import streamlit as st
import pandas as pd
import pdfplumber
import re
import io

st.set_page_config(page_title="Extractor F.931 Profesional", layout="wide")
st.title("📑 Consolidador Multiempresa F.931")

def limpiar_monto(texto):
    if not texto: return 0.0
    try:
        # Extrae solo dígitos, comas, puntos y signos menos
        valor = re.sub(r'[^\d,.-]', '', texto)
        if not valor: return 0.0
        # Normaliza formato contable (punto para miles, coma para decimales)
        if ',' in valor and '.' in valor:
            valor = valor.replace('.', '').replace(',', '.')
        elif ',' in valor:
            valor = valor.replace(',', '.')
        return float(valor)
    except:
        return 0.0

def procesar_931(file):
    with pdfplumber.open(file) as pdf:
        txt = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        res = {}
        
        # 1. Identificación básica (Razón Social, CUIT, Período)
        rs = re.search(r"(?:Social|Razon Social):\s*\n?\s*(.*)", txt, re.I)
        res['Empresa'] = rs.group(1).strip() if rs else "Empresa No Identificada"
        
        cuit = re.search(r"(\d{2}-\d{8}-\d)", txt)
        res['CUIT'] = cuit.group(1) if cuit else "S/D"
        
        per = re.search(r"(\d{2}/\d{4})", txt)
        res['Mes - Año'] = per.group(1) if per else "S/D"
        
        emp = re.search(r"nomi\w*\s*[:\s]*(\d+)", txt, re.I)
        res['Empleados'] = emp.group(1) if emp else "0"

        # 2. Remuneraciones (Búsqueda más flexible)
        for r in [1, 4, 8, 9, 10]:
            # Busca "Rem. X" seguido de cualquier cosa hasta encontrar un número con decimales
            m = re.search(rf"Rem\.\s*{r}.*?([\d.]+,\d{{2}})", txt, re.DOTALL)
            res[f'Rem {r}'] = limpiar_monto(m.group(1)) if m else 0.0

        # 3. Detracciones y Decreto 394
        det = re.search(rf"Detraido.*?([\d.]+,\d{{2}})", txt, re.DOTALL)
        res['Ley 27430 Detraido'] = limpiar_monto(det.group(1)) if det else 0.0
        
        dec = re.search(rf"394.*?([\d.]+,\d{{2}})", txt, re.DOTALL)
        res['Dec 394'] = limpiar_monto(dec.group(1)) if dec else 0.0

        # 4. EXTRACCIÓN POR CÓDIGOS (La clave para evitar el 0.0)
        # Buscamos el código y capturamos el primer valor que parezca dinero (xxx,xx)
        patrones = {
            '351-Contrib SS Total': r"351-.*?Contribuciones.*?Seguridad Social.*?([\d.]+,\d{{2}})",
            '351-SIPA': r"S\.?S\.?\s*SIPA.*?([\d.]+,\d{{2}})",
            '351-No SIPA': r"S\.?S\.?\s*No\s*SIPA.*?([\d.]+,\d{{2}})",
            '301-Aportes SS': r"301-.*?Aportes.*?Seguridad Social.*?([\d.]+,\d{{2}})",
            '352-Contrib OS': r"352-.*?Contrib.*?Obra Social.*?([\d.]+,\d{{2}})",
            '302-Aportes OS': r"302-.*?Aportes.*?Obra Social.*?([\d.]+,\d{{2}})",
            '312-LRT': r"312-.*?L\.?R\.?T.*?([\d.]+,\d{{2}})",
            '028-Vida': r"028-.*?Seguro.*?Vida.*?([\d.]+,\d{{2}})"
        }
        
        for clave, regex in patrones.items():
            # El secreto es re.DOTALL para que busque incluso si hay saltos de línea
            match = re.search(regex, txt, re.IGNORECASE | re.DOTALL)
            res[clave] = limpiar_monto(match.group(1)) if match else 0.0
            
        return res

# --- INTERFAZ ---
files = st.file_uploader("Cargá tus F.931 (PDF)", type="pdf", accept_multiple_files=True)

if files:
    try:
        data = [procesar_931(f) for f in files]
        df = pd.DataFrame(data)
        
        if not df.empty:
            empresas = df['Empresa'].unique()
            emp_sel = st.selectbox("Seleccioná la empresa:", empresas)
            
            # Trasponemos para que los meses sean columnas
            df_final = df[df['Empresa'] == emp_sel].set_index('Mes - Año').T
            
            st.write(f"### Planilla Consolidada: {emp_sel}")
            st.dataframe(df_final)
            
            # Generación de Excel
            buffer = io.BytesIO()
            df_final.to_excel(buffer, sheet_name='Consolidado_931')
            st.download_button("📥 Descargar Excel", buffer.getvalue(), f"Planilla_931_{emp_sel}.xlsx")
            
    except Exception as e:
        st.error(f"Error de procesamiento: {e}")
