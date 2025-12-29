import streamlit as st
import pandas as pd
import pdfplumber
import re
import io

st.set_page_config(page_title="Extractor Universal F.931", layout="wide")
st.title("📑 Consolidador Multiempresa F.931")

def limpiar_monto(texto):
    if not texto: return 0.0
    valor = re.sub(r'[^\d,]', '', texto)
    return float(valor.replace(',', '.')) if valor else 0.0

def procesar_931(file):
    with pdfplumber.open(file) as pdf:
        txt = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        res = {}
        
        # Identificación básica
        rs = re.search(r"(?:Social|Razon Social):\s*\n?\s*(.*)", txt, re.IGNORECASE)
        res['Empresa'] = rs.group(1).strip() if rs else "No identificado"
        
        cuit = re.search(r"(\d{2}-\d{8}-\d)", txt)
        res['CUIT'] = cuit.group(1) if cuit else "S/D"
        
        periodo = re.search(r"(\d{2}/\d{4})", txt)
        res['Mes - Año'] = periodo.group(1) if periodo else "S/D"
        
        emp = re.search(r"(?:nómina|nomina)\s*[:\s]*(\d+)", txt, re.IGNORECASE)
        res['Empleados'] = emp.group(1) if emp else "0"

        # Remuneraciones
        for r in [1, 4, 8, 9, 10]:
            m = re.search(f"Rem\. {r}[:\s]+([\d.,]+)", txt)
            res[f'Rem {r}'] = limpiar_monto(m.group(1)) if m else 0.0

        # Monto Detraído y Decreto 394
        det = re.search(r"Detraido[:\s]+([\d.,]+)", txt)
        res['Ley 27430 Detraido'] = limpiar_monto(det.group(1)) if det else 0.0
        
        dec = re.search(r"Dec\.?\s*394[:\s]+([\d.,]+)", txt)
        res['Dec 394'] = limpiar_monto(dec.group(1)) if dec else 0.0

        # CONCEPTOS RESALTADOS (Búsqueda robusta)
        # 1. Seguridad Social
        ss_total = re.search(r"351-Contribuciones de Seguridad Social\s+([\d.,]+)", txt)
        res['351-Contrib SS Total'] = limpiar_monto(ss_total.group(1)) if ss_total else 0.0
        
        sipa = re.search(r"S\.S\. SIPA\s+([\d.,]+)", txt)
        res['351-SIPA'] = limpiar_monto(sipa.group(1)) if sipa else 0.0
        
        no_sipa = re.search(r"S\.S\. No SIPA\s+([\d.,]+)", txt)
        res['351-No SIPA'] = limpiar_monto(no_sipa.group(1)) if no_sipa else 0.0
        
        aportes_ss = re.search(r"301-Aportes de Seguridad Social\s+([\d.,]+)", txt)
        res['301-Aportes SS'] = limpiar_monto(aportes_ss.group(1)) if aportes_ss else 0.0

        # 2. Obra Social
        contrib_os = re.search(r"352-\s*Contribuciones de Obra Social\s+([\d.,]+)", txt)
        res['352-Contrib OS'] = limpiar_monto(contrib_os.group(1)) if contrib_os else 0.0
        
        aportes_os = re.search(r"302-Aportes de Obra Social\s+([\d.,]+)", txt)
        res['302-Aportes OS'] = limpiar_monto(aportes_os.group(1)) if aportes_os else 0.0

        # 3. Otros
        lrt = re.search(r"312-L\.?R\.?T\.?\s+([\d.,]+)", txt)
        res['312-LRT'] = limpiar_monto(lrt.group(1)) if lrt else 0.0
        
        vida = re.search(r"028-Seguro Colectivo de Vida Obligatorio\s+([\d.,]+)", txt)
        res['028-Vida'] = limpiar_monto(vida.group(1)) if vida else 0.0
            
        return res

files = st.file_uploader("Subí tus archivos PDF", type="pdf", accept_multiple_files=True)
if files:
    data = [procesar_931(f) for f in files]
    df = pd.DataFrame(data)
    
    empresas = df['Empresa'].unique()
    sel = st.selectbox("Seleccioná Empresa:", empresas)
    df_f = df[df['Empresa'] == sel].set_index('Mes - Año').T
    
    st.dataframe(df_f.style.format("{:,.2f}"))
    
    towrite = io.BytesIO()
    df_f.to_excel(towrite, index=True)
    st.download_button("📥 Descargar Excel", towrite.getvalue(), f"Planilla_{sel}.xlsx")
