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
        # Extrae solo números y comas/puntos finales
        valor = re.sub(r'[^\d,]', '', texto)
        if not valor: return 0.0
        return float(valor.replace(',', '.'))
    except:
        return 0.0

def procesar_931(file):
    with pdfplumber.open(file) as pdf:
        txt = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        res = {}
        
        # Identificación (Uso de 'get' para evitar errores)
        rs = re.search(r"Social:\s*\n?\s*(.*)", txt)
        res['Empresa'] = rs.group(1).strip() if rs else "Empresa Desconocida"
        
        cuit = re.search(r"(\d{2}-\d{8}-\d)", txt)
        res['CUIT'] = cuit.group(1) if cuit else "S/D"
        
        per = re.search(r"(\d{2}/\d{4})", txt)
        res['Mes - Año'] = per.group(1) if per else "S/D"
        
        emp = re.search(r"nomi\w*\s*[:\s]*(\d+)", txt, re.I)
        res['Empleados'] = emp.group(1) if emp else "0"

        # Remuneraciones (1, 4, 8, 9, 10)
        for r in [1, 4, 8, 9, 10]:
            m = re.search(f"Rem\. {r}[:\s]+([\d.,]+)", txt)
            res[f'Rem {r}'] = limpiar_monto(m.group(1)) if m else 0.0

        # Detracciones y Leyes
        det = re.search(r"Detraido[:\s]+([\d.,]+)", txt)
        res['Ley 27430 Detraido'] = limpiar_monto(det.group(1)) if det else 0.0
        
        dec = re.search(r"394[:\s]+([\d.,]+)", txt)
        res['Dec 394'] = limpiar_monto(dec.group(1)) if dec else 0.0

        # --- EXTRACCIÓN ROBUSTA DE CONCEPTOS RESALTADOS ---
        # Buscamos por código numérico y proximidad de texto
        conceptos = {
            '351-Contrib SS Total': r"351-?Contribuciones de Seguridad Social\s+([\d.,]+)",
            '351-SIPA': r"S\.?S\.? SIPA\s+([\d.,]+)",
            '351-No SIPA': r"S\.?S\.? No SIPA\s+([\d.,]+)",
            '301-Aportes SS': r"301-?Aportes de Seguridad Social\s+([\d.,]+)",
            '352-Contrib OS': r"352-?\s*Contribuciones de Obra Social\s+([\d.,]+)",
            '302-Aportes OS': r"302-?Aportes de Obra Social\s+([\d.,]+)",
            '312-LRT': r"312-?L\.?R\.?T\.?\s+([\d.,]+)",
            '028-Vida': r"028-?Seguro Colectivo de Vida Obligatorio\s+([\d.,]+)"
        }
        
        for clave, regex in conceptos.items():
            match = re.search(regex, txt, re.IGNORECASE)
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
            emp_sel = st.selectbox("Seleccioná la empresa para ver la planilla:", empresas)
            
            # Filtrar y trasponer para que los meses queden arriba
            df_final = df[df['Empresa'] == emp_sel].set_index('Mes - Año').T
            
            st.write(f"### Planilla Consolidada: {emp_sel}")
            # Mostramos la tabla formateada para que los números se vean bien
            st.dataframe(df_final.style.format("{:,.2f}"))
            
            # Botón de Descarga Excel
            buffer = io.BytesIO()
            df_final.to_excel(buffer)
            st.download_button("📥 Descargar Excel", buffer.getvalue(), f"Planilla_931_{emp_sel}.xlsx")
            
    except Exception as e:
        st.error(f"Error detectado: {e}")
 
