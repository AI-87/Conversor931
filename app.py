
import streamlit as st
import pandas as pd
import pdfplumber
import re
import io

st.set_page_config(page_title="Extractor F.931 - Roma360", layout="wide")
st.title("📊 Extractor de Datos F.931")

def limpiar_monto(texto):
    if not texto: return 0.0
    return float(texto.replace('.', '').replace(',', '.'))

def procesar_931(file):
    with pdfplumber.open(file) as pdf:
        txt = "\n".join([p.extract_text() for p in pdf.pages])
        res = {}
        
        # Datos de Cabecera
        res['Apellido y Nombre o Razon Social:'] = re.search(r"Social:\s*\n(.*)", txt).group(1).strip()
        res['CUIT'] = re.search(r"(\d{2}-\d{8}-\d)", txt).group(1)
        res['Mes - Año'] = re.search(r"(\d{2}/\d{4})", txt).group(1)
        res['Empleados en nomina'] = re.search(r"nómina\s*t?:\s*(\d+)", txt).group(1)
        
        # Remuneraciones
        for r in [1, 4, 8, 9, 10]:
            match = re.search(f"Rem\. {r}[:\s]+([\d.,]+)", txt)
            res[f'Suma de Rem. {r}'] = limpiar_monto(match.group(1)) if match else 0.0
        
        # Detracciones y Decretos
        res['Ley 27430 - Monto Total Detraido'] = limpiar_monto(re.search(r"Detraido:\s+([\d.,]+)", txt).group(1))
        pago_394 = re.search(r"Dec\. 394:\s+([\d.,]+)", txt)
        res['Pago a Cuenta Dec, 394'] = limpiar_monto(pago_394.group(1)) if pago_394 else 0.0
        
        # Códigos de Pago y Contribuciones
        res['351 - Contribuciones de Seguridad Social'] = limpiar_monto(re.search(r"351-Contribuciones de Seguridad Social\s+([\d.,]+)", txt).group(1))
        res['351 - Contribuciones de S.S Sipa'] = limpiar_monto(re.search(r"S\.S\. SIPA\s+([\d.,]+)", txt).group(1))
        res['351 - Contribuciones de S.S No Sipa'] = limpiar_monto(re.search(r"S\.S\. No SIPA\s+([\d.,]+)", txt).group(1))
        res['301 - Aportes de Seguridad Social'] = limpiar_monto(re.search(r"301-Aportes de Seguridad Social\s+([\d.,]+)", txt).group(1))
        res['352 - Contribuciones de Obra Social'] = limpiar_monto(re.search(r"352- Contribuciones de Obra Social\s+([\d.,]+)", txt).group(1))
        res['302 - Aportes de Obra Social'] = limpiar_monto(re.search(r"302-Aportes de Obra Social\s+([\d.,]+)", txt).group(1))
        res['312 - LRT'] = limpiar_monto(re.search(r"312-L\.?R\.?T\s+([\d.,]+)", txt).group(1))
        res['028 - Seguro Colectiuvo de Vida Obligatorio'] = limpiar_monto(re.search(r"028-Seguro Colectivo de Vida Obligatorio\s+([\d.,]+)", txt).group(1))
        
        return res

files = st.file_uploader("Subí tus archivos PDF", type="pdf", accept_multiple_files=True)
if files:
    data = [procesar_931(f) for f in files]
    df = pd.DataFrame(data).set_index('Mes - Año').T
    st.dataframe(df)
    
    towrite = io.BytesIO()
    df.to_excel(towrite, index=True, sheet_name='Planilla_931')
    st.download_button("📥 Descargar Excel Consolidado", towrite.getvalue(), "Planilla_Anual_931.xlsx")
