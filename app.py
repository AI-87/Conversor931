import streamlit as st
import pandas as pd
import pdfplumber
import re
import io

st.set_page_config(page_title="Extractor F.931 Profesional", layout="wide")
st.title("📑 Consolidador Multiempresa F.931")

def limpiar_monto(texto):
    if not texto:
        return 0.0
    try:
        # Extrae solo dígitos, comas, puntos y signos menos
        valor = re.sub(r'[^\d,.-]', '', texto)
        if not valor:
            return 0.0
        # Normaliza formato contable (punto miles, coma decimal)
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
        
        # 1. Identificación básica (Razón Social, CUIT, Período, Empleados)
        rs = re.search(r"Raz[oó]n Social:\s*\n?\s*(.*)", txt)
        res['Empresa'] = rs.group(1).strip() if rs else "Empresa No Identificada"
        
        cuit = re.search(r"(\d{2}-\d{8}-\d)", txt)
        res['CUIT'] = cuit.group(1) if cuit else "S/D"
        
        per = re.search(r"Mes\s*-\s*A[oó]\s*(\d{2}/\d{4})", txt, re.I)
        res['Mes - Año'] = per.group(1) if per else "S/D"
        
        emp = re.search(r"Empleados en n[oó]mina:\s*(\d+)", txt, re.I)
        res['Empleados'] = emp.group(1) if emp else "0"

        # 2. Remuneraciones (1, 4, 8, 9, 10)
        for r in [1, 4, 8, 9, 10]:
            m = re.search(rf"Suma de Rem\. {r}:\s*([\d.]+,\d{{2}})", txt)
            res[f'Rem {r}'] = limpiar_monto(m.group(1)) if m else 0.0

        # 3. Ley 27.430 y Dec. 394
        det = re.search(r"Ley\s*27\.?430.*?Detra[ií]do[:\s]+([\d.]+,\d{2})", txt, re.I | re.DOTALL)
        res['Ley 27430 Detraido'] = limpiar_monto(det.group(1)) if det else 0.0
        
        dec = re.search(r"Pago a Cuenta\s*Dec\.?\s*394[:\s]+([\d.]+,\d{2})", txt, re.I | re.DOTALL)
        res['Dec 394'] = limpiar_monto(dec.group(1)) if dec else 0.0

        # 4. Conceptos AFIP en VIII - MONTOS QUE SE INGRESAN
        patrones = {
            '351-Contrib SS Total': r"351\s*-\s*Contribuciones\s+de\s+Seguridad\s+Social\s+([\d.]+,\d{2})",
            '351-SIPA': r"351\s+Contribuciones\s+S\.?S\.?\s*SIPA\s+([\d.]+,\d{2})",
            '351-No SIPA': r"351\s+Contribuciones\s+S\.?S\.?\s*No\s*SIPA\s+([\d.]+,\d{2})",
            '301-Aportes SS': r"301\s*-\s*Aportes\s+de\s+Seguridad\s+Social\s+([\d.]+,\d{2})",
            '352-Contrib OS': r"352\s*-\s*Contribuciones\s+de\s+Obra\s+Social\s+([\d.]+,\d{2})",
            '302-Aportes OS': r"302\s*-\s*Aportes\s+de\s+Obra\s+Social\s+([\d.]+,\d{2})",
            '312-LRT': r"312\s*-\s*L\.?R\.?T\.?\s+([\d.]+,\d{2})",
            '028-Vida': r"028\s*-\s*Seguro\s+Colectivo\s+de\s+Vida\s+Obligatorio\s+([\d.]+,\d{2})"
        }
        
        for clave, regex in patrones.items():
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
            # descartar filas sin período para evitar S/D duplicado
            df = df[df['Mes - Año'] != "S/D"]
            
            if df.empty:
                st.warning("No se pudo identificar el período (Mes - Año) en los PDF.")
            else:
                empresas = df['Empresa'].unique()
                emp_sel = st.selectbox("Seleccioná la empresa:", empresas)
                
                # Filtrar por empresa, evitar meses duplicados y trasponer
                df_emp = df[df['Empresa'] == emp_sel].drop_duplicates(subset=['Mes - Año'])
                df_final = df_emp.set_index('Mes - Año').T
                
                st.write(f"### Planilla Consolidada: {emp_sel}")
                st.dataframe(df_final)
                
                # Generación de Excel
                buffer = io.BytesIO()
                df_final.to_excel(buffer, sheet_name='Consolidado_931')
                st.download_button(
                    "📥 Descargar Excel",
                    buffer.getvalue(),
                    f"Planilla_931_{emp_sel}.xlsx"
                )
    except Exception as e:
        st.error(f"Error de procesamiento: {e}")

