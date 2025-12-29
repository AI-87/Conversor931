
import streamlit as st
import pandas as pd
import pdfplumber
import re
import io

st.set_page_config(page_title="Extractor Universal F.931", layout="wide")
st.title("📑 Extractor de Datos F.931 - Universal")
st.write("Subí los PDF de cualquier empresa para generar la planilla.")

def limpiar_monto(texto):
    if not texto: return 0.0
    valor = re.sub(r'[^\d,]', '', texto)
    return float(valor.replace(',', '.')) if valor else 0.0

def procesar_931(file):
    with pdfplumber.open(file) as pdf:
        txt = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        res = {}
        
        # 1. Identificación Flexible
        rs_match = re.search(r"(?:Social|Razon Social):\s*\n?\s*(.*)", txt, re.IGNORECASE)
        res['Apellido y Nombre o Razon Social:'] = rs_match.group(1).strip() if rs_match else "S/D"
        
        cuit = re.search(r"(\d{2}-\d{8}-\d)", txt)
        res['CUIT'] = cuit.group(1) if cuit else "S/D"
        
        periodo = re.search(r"(\d{2}/\d{4})", txt)
        res['Mes - Año'] = periodo.group(1) if periodo else "S/D"
        
        emp = re.search(r"(?:nómina|nominat|nomina)\s*[:\s]*(\d+)", txt, re.IGNORECASE)
        res['Empleados en nomina'] = emp.group(1) if emp else "0"
        
        # 2. Remuneraciones
        for r in [1, 4, 8, 9, 10]:
            match = re.search(f"Rem\. {r}[:\s]+([\d.,]+)", txt)
            res[f'Suma de Rem. {r}'] = limpiar_monto(match.group(1)) if match else 0.0
        
        # 3. Detracciones y Decretos
        detraido = re.search(r"Detraido[:\s]+([\d.,]+)", txt)
        res['Ley 27430 - Monto Total Detraido'] = limpiar_monto(detraido.group(1)) if detraido else 0.0
        
        p394 = re.search(r"(?:Dec\.?\s*394|Decreto 394)[:\s]+([\d.,]+)", txt)
        res['Pago a Cuenta Dec, 394'] = limpiar_monto(p394.group(1)) if p394 else 0.0
        
        # 4. Códigos de Pago y Contribuciones (Regex Mejoradas)
        conceptos = {
            '351 -Contribuciones de Seguridad Social': r"351-?Contribuciones de Seguridad Social\s+([\d.,]+)",
            '351 - Contribuciones de S.S Sipa': r"S\.?S\.? SIPA\s+([\d.,]+)",
            '351 - Contribuciones de S.S No Sipa': r"S\.?S\.? No SIPA\s+([\d.,]+)",
            '301 - Aportes de Seguridad Social': r"301-?Aportes de Seguridad Social\s+([\d.,]+)",
            '352 - Contribuciones de Obra Social': r"352-?\s*Contribuciones de Obra Social\s+([\d.,]+)",
            '302 - Aportes de Obra Social': r"302-?Aportes de Obra Social\s+([\d.,]+)",
            '312 - LRT': r"312-?L\.?R\.?T\.?\s+([\d.,]+)",
            '028 - Seguro Colectiuvo de Vida Obligatorio': r"028-?Seguro Colectivo de Vida Obligatorio\s+([\d.,]+)"
        }
        
        for nombre, patron in conceptos.items():
            match = re.search(patron, txt, re.IGNORECASE)
            res[nombre] = limpiar_monto(match.group(1)) if match else 0.0
            
        return res

files = st.file_uploader("Subí tus archivos PDF", type="pdf", accept_multiple_files=True)

if files:
    try:
        data = [procesar_931(f) for f in files]
        df = pd.DataFrame(data)
        
        # Filtro por empresa por si subís varias juntas
        if not df.empty:
            empresas = df['Apellido y Nombre o Razon Social:'].unique()
            empresa_sel = st.selectbox("Seleccioná la empresa:", empresas)
            
            df_final = df[df['Apellido y Nombre o Razon Social:'] == empresa_sel].set_index('Mes - Año').T
            st.dataframe(df_final)
            
            # Exportar a Excel
            towrite = io.BytesIO()
            df_final.to_excel(towrite, index=True, sheet_name='Planilla_F931')
            st.download_button("📥 Descargar Planilla Excel", towrite.getvalue(), "Planilla_Anual_931.xlsx")
    except Exception as e:
        st.error(f"Error al procesar los archivos: {e}")
