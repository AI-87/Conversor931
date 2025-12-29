import streamlit as st
import pandas as pd
import pdfplumber
import re
import io

st.set_page_config(page_title="Extractor F.931 Profesional", layout="wide")
st.title("📑 Consolidador Multiempresa F.931")

def limpiar_monto(texto):
    if not texto: return 0.0
    valor = re.sub(r'[^\d,]', '', texto)
    return float(valor.replace(',', '.')) if valor else 0.0

def extraer_con_codigo(texto, codigo, fallback_regex):
    # Primero intenta buscar por el código numérico oficial de AFIP
    match = re.search(rf"{codigo}.*?([\d.,]+)", texto)
    if match:
        return limpiar_monto(match.group(1))
    # Si falla, intenta con una descripción general
    match_alt = re.search(fallback_regex, texto, re.IGNORECASE)
    return limpiar_monto(match_alt.group(1)) if match_alt else 0.0

def procesar_931(file):
    with pdfplumber.open(file) as pdf:
        txt = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        res = {}
        
        # Datos Identificatorios (Red de seguridad para que no falle)
        rs = re.search(r"Social:\s*\n?\s*(.*)", txt)
        res['Empresa'] = rs.group(1).strip() if rs else "Sin Nombre"
        
        cuit = re.search(r"(\d{2}-\d{8}-\d)", txt)
        res['CUIT'] = cuit.group(1) if cuit else "S/D"
        
        periodo = re.search(r"(\d{2}/\d{4})", txt)
        res['Mes - Año'] = periodo.group(1) if periodo else "S/D"
        
        emp = re.search(r"nomi\w*\s*[:\s]*(\d+)", txt, re.I)
        res['Empleados'] = int(emp.group(1)) if emp else 0

        # Remuneraciones
        for r in [1, 4, 8, 9, 10]:
            m = re.search(f"Rem\. {r}[:\s]+([\d.,]+)", txt)
            res[f'Rem {r}'] = limpiar_monto(m.group(1)) if m else 0.0

        # Detracciones (Resaltados en tu planilla)
        res['Ley 27430 Detraido'] = extraer_con_codigo(txt, "Detraido", r"Detraido[:\s]+([\d.,]+)")
        res['Dec 394'] = extraer_con_codigo(txt, "394", r"394[:\s]+([\d.,]+)")

        # CONCEPTOS DE SEGURIDAD Y OBRA SOCIAL (Uso de códigos 351, 301, 352, 302, 312)
        res['351-Contrib SS Total'] = extraer_con_codigo(txt, "351-Contribuciones de Seguridad Social", r"Social\s+([\d.,]+)\s+a1")
        res['351-SIPA'] = extraer_con_codigo(txt, "SIPA", r"SIPA\s+([\d.,]+)")
        res['351-No SIPA'] = extraer_con_codigo(txt, "No SIPA", r"No SIPA\s+([\d.,]+)")
        res['301-Aportes SS'] = extraer_con_codigo(txt, "301", r"301-?Aportes.*?Seguridad Social\s+([\d.,]+)")
        
        res['352-Contrib OS'] = extraer_con_codigo(txt, "352", r"352-?Contrib.*?Obra Social\s+([\d.,]+)")
        res['302-Aportes OS'] = extraer_con_codigo(txt, "302", r"302-?Aportes.*?Obra Social\s+([\d.,]+)")
        
        res['312-LRT'] = extraer_con_codigo(txt, "312", r"312-?L\.?R\.?T\.?\s+([\d.,]+)")
        res['028-Vida'] = extraer_con_codigo(txt, "028", r"028-?Seguro.*?Vida\s+([\d.,]+)")
            
        return res

# --- Interfaz de Usuario ---
files = st.file_uploader("Cargá tus F.931 (PDF)", type="pdf", accept_multiple_files=True)

if files:
    try:
        data = [procesar_931(f) for f in files]
        df = pd.DataFrame(data)
        
        # Selección de Empresa (para no mezclar cuits diferentes)
        empresas_disponibles = df['Empresa'].unique()
        empresa_elegida = st.selectbox("Seleccioná la empresa para ver la planilla:", empresas_disponibles)
        
        # Filtrar y trasponer para que los meses queden arriba (columnas)
        df_final = df[df['Empresa'] == empresa_elegida].set_index('Mes - Año').sort_index().T
        
        st.write(f"### Planilla Consolidada: {empresa_elegida}")
        st.dataframe(df_final.style.format("{:,.2f}"))
        
        # Descarga
        buffer = io.BytesIO()
        df_final.to_excel(buffer)
        st.download_button("📥 Descargar Planilla Excel", buffer.getvalue(), f"Planilla_{empresa_elegida}.xlsx")
        
    except Exception as e:
        st.error(f"Error crítico de procesamiento: {e}")
