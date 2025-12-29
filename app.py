import streamlit as st
import pandas as pd
import pdfplumber
import re
import io

st.set_page_config(page_title="Extractor Universal F.931", layout="wide")
st.title("📑 Consolidador Multiempresa F.931")
st.write("Subí los PDF de cualquier empresa. El sistema agrupará los datos por Mes/Año automáticamente.")

def limpiar_monto(texto):
    if not texto: return 0.0
    # Remueve todo lo que no sea número o coma
    valor = re.sub(r'[^\d,]', '', texto)
    return float(valor.replace(',', '.')) if valor else 0.0

def procesar_931(file):
    with pdfplumber.open(file) as pdf:
        # Extraemos todo el texto del formulario
        txt = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        res = {}
        
        # 1. Identificación (Busca lo que esté después de 'Social:')
        rs_match = re.search(r"(?:Social|Razon Social):\s*\n?\s*(.*)", txt, re.IGNORECASE)
        res['Empresa'] = rs_match.group(1).strip() if rs_match else "No identificada"
        
        cuit = re.search(r"(\d{2}-\d{8}-\d)", txt)
        res['CUIT'] = cuit.group(1) if cuit else "S/D"
        
        periodo = re.search(r"(\d{2}/\d{4})", txt)
        res['Mes - Año'] = periodo.group(1) if periodo else "S/D"
        
        emp = re.search(r"(?:nómina|nominat|nomina)\s*[:\s]*(\d+)", txt, re.IGNORECASE)
        res['Empleados'] = int(emp.group(1)) if emp else 0
        
        # 2. Remuneraciones (1, 4, 8, 9 y 10)
        for r in [1, 4, 8, 9, 10]:
            match = re.search(f"Rem\. {r}[:\s]+([\d.,]+)", txt)
            res[f'Suma de Rem. {r}'] = limpiar_monto(match.group(1)) if match else 0.0
        
        # 3. Detracciones y Beneficios
        detraido = re.search(r"Detraido[:\s]+([\d.,]+)", txt)
        res['Ley 27430 - Monto Detraído'] = limpiar_monto(detraido.group(1)) if detraido else 0.0
        
        p394 = re.search(r"(?:Dec\.?\s*394|Decreto 394)[:\s]+([\d.,]+)", txt)
        res['Pago a Cuenta Dec. 394'] = limpiar_monto(p394.group(1)) if p394 else 0.0
        
        # 4. Códigos de Pago (Seguridad Social y Obra Social)
        # Buscamos por el nombre del concepto o el código del sistema
        conceptos = {
            '351-Contrib S.S. Total': r"351-?Contribuciones de Seguridad Social\s+([\d.,]+)",
            '351-SIPA': r"S\.?S\.? SIPA\s+([\d.,]+)",
            '351-No SIPA': r"S\.?S\.? No SIPA\s+([\d.,]+)",
            '301-Aportes S.S.': r"301-?Aportes de Seguridad Social\s+([\d.,]+)",
            '352-Contrib O.S.': r"352-?\s*Contribuciones de Obra Social\s+([\d.,]+)",
            '302-Aportes O.S.': r"302-?Aportes de Obra Social\s+([\d.,]+)",
            '312-LRT': r"312-?L\.?R\.?T\.?\s+([\d.,]+)",
            '028-Seguro Vida': r"028-?Seguro Colectivo de Vida Obligatorio\s+([\d.,]+)"
        }
        
        for nombre, patron in conceptos.items():
            match = re.search(patron, txt, re.IGNORECASE)
            res[nombre] = limpiar_monto(match.group(1)) if match else 0.0

        # 5. Retenciones aplicadas (en negativo como pediste)
        ret_ss = re.search(r"Retenciones aplicadas a Seguridad Social\s+([\d.,]+)", txt)
        res['Retenciones Aplicadas S.S.'] = -limpiar_monto(ret_ss.group(1)) if ret_ss else 0.0
        
        ret_os = re.search(r"Retenciones aplicadas a Obra Social\s+([\d.,]+)", txt)
        res['Retenciones Aplicadas O.S.'] = -limpiar_monto(ret_os.group(1)) if ret_os else 0.0
            
        return res

files = st.file_uploader("Cargá uno o varios F.931 (PDF)", type="pdf", accept_multiple_files=True)

if files:
    try:
        data = [procesar_931(f) for f in files]
        df = pd.DataFrame(data)
        
        # Si hay varias empresas, mostramos un filtro
        empresas = df['Empresa'].unique()
        empresa_sel = st.selectbox("Seleccioná la empresa para ver la planilla:", empresas)
        
        df_filtrado = df[df['Empresa'] == empresa_sel].set_index('Mes - Año').sort_index().T
        
        st.write(f"### Planilla Anual: {empresa_sel}")
        st.dataframe(df_filtrado.style.format("{:,.2f}"))
        
        # Excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_filtrado.to_excel(writer, sheet_name='931_Consolidado')
        
        st.download_button(
            label="📥 Descargar Excel",
            data=buffer.getvalue(),
            file_name=f"Planilla_931_{empresa_sel.replace(' ', '_')}.xlsx",
            mime="application/vnd.ms-excel"
        )
    except Exception as e:
        st.error(f"Se produjo un error al leer los archivos: {e}")
