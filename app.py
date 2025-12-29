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
        # Extrae solo números, comas y puntos
        valor = re.sub(r'[^\d,.]', '', texto)
        # Normaliza formato contable argentino
        if ',' in valor and '.' in valor:
            valor = valor.replace('.', '').replace(',', '.')
        elif ',' in valor:
            valor = valor.replace(',', '.')
        return float(valor) if valor else 0.0
    except:
        return 0.0

def procesar_931(file):
    with pdfplumber.open(file) as pdf:
        txt = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        res = {}
        
        # Identificación segura
        rs = re.search(r"Raz[oó]n Social:\s*\n?\s*(.*)", txt)
        res['Empresa'] = rs.group(1).strip() if rs else "Empresa No Identificada"
        
        cuit = re.search(r"(\d{2}-\d{8}-\d)", txt)
        res['CUIT'] = cuit.group(1) if cuit else "S/D"
        
        # Mes y Año (ej: 11/2025 o 11 2025)
        per = re.search(r"Mes\s*-\s*A[oó]\s*(\d{2})\s*/?\s*(\d{4})", txt, re.I)
        if per:
            res['Mes - Año'] = f"{per.group(1)}/{per.group(2)}"
        else:
            res['Mes - Año'] = "S/D"
        
        emp = re.search(r"Empleados en n[oó]mina:\s*(\d+)", txt, re.I)
        res['Empleados'] = emp.group(1) if emp else "0"

        # Remuneraciones (1, 4, 8, 9, 10)
        for r in [1, 4, 8, 9, 10]:
            m = re.search(rf"Suma de Rem\. {r}:\s*([\d.,]+)", txt)
            res[f'Rem {r}'] = limpiar_monto(m.group(1)) if m else 0.0

        # Ley 27430 y Dec. 394
        det = re.search(r"Ley\s*27\.?430.*?Detra[ií]do[:\s]+([\d.,]+)", txt, re.I)
        res['Ley 27430 Detraido'] = limpiar_monto(det.group(1)) if det else 0.0
        
        dec = re.search(r"Pago a Cuenta\s*Dec\.?\s*394[:\s]+([\d.,]+)", txt, re.I)
        res['Dec 394'] = limpiar_monto(dec.group(1)) if dec else 0.0

        # Conceptos AFIP (bloque VIII - MONTOS QUE SE INGRESAN)
        regex_conceptos = {
            '351-Contrib SS Total': r"351\s*-\s*Contribuciones de Seguridad Social\s+([\d.,]+)",
            '351-SIPA': r"351\s+Contribuciones S\.?S\.?\s*SIPA\s+([\d.,]+)",
            '351-No SIPA': r"351\s+Contribuciones S\.?S\.?\s*No\s+SIPA\s+([\d.,]+)",
            '301-Aportes SS': r"301\s*-\s*Aportes de Seguridad Social\s+([\d.,]+)",
            '352-Contrib OS': r"352\s+Contribuciones de Obra Social\s+([\d.,]+)",
            '302-Aportes OS': r"302\s*-\s*Aportes de Obra Social\s+([\d.,]+)",
            '312-LRT': r"312\s*-\s*L\.?R\.?T\.?\s+([\d.,]+)",
            '028-Vida': r"028\s*-\s*Seguro Colectivo de Vida Obligatorio\s+([\d.,]+)",
        }
        
        for clave, patron in regex_conceptos.items():
            match = re.search(patron, txt, re.IGNORECASE)
            res[clave] = limpiar_monto(match.group(1)) if match else 0.0
            
        return res

# --- INTERFAZ ---
files = st.file_uploader("Cargá tus F.931 (PDF)", type="pdf", accept_multiple_files=True)

if files:
    try:
        data = [procesar_931(f) for f in files]

        # Asegurar que todas las claves existan
        campos_clave = [
            'Empresa','CUIT','Mes - Año','Empleados',
            'Rem 1','Rem 4','Rem 8','Rem 9','Rem 10',
            'Ley 27430 Detraido','Dec 394',
            '351-Contrib SS Total','351-SIPA','351-No SIPA',
            '301-Aportes SS','352-Contrib OS','302-Aportes OS',
            '312-LRT','028-Vida'
        ]
        for d in data:
            for c in campos_clave:
                d.setdefault(c, 0.0 if c not in ['Empresa','CUIT','Mes - Año'] else "")

        df = pd.DataFrame(data)

        if not df.empty:
            # descartar filas sin período válido
            df = df[df['Mes - Año'] != "S/D"]

            empresas = df['Empresa'].replace("", "Empresa No Identificada").unique()
            emp_sel = st.selectbox("Seleccioná la empresa:", empresas)

            df_filtrado = df[df['Empresa'].replace("", "Empresa No Identificada") == emp_sel]

            # asegurar que Mes - Año no se repita
            df_filtrado = df_filtrado.drop_duplicates(subset=['Mes - Año'])

            df_final = df_filtrado.set_index('Mes - Año').T
            
            st.write(f"### Planilla Consolidada: {emp_sel}")
            st.dataframe(df_final, use_container_width=True)
            
            # Generación de Excel
            buffer = io.BytesIO()
            df_final.to_excel(buffer, sheet_name='Consolidado_931')
            
            st.download_button(
                label="📥 Descargar Excel",
                data=buffer.getvalue(),
                file_name=f"931_{emp_sel.replace(' ', '_')}.xlsx",
                mime="application/vnd.ms-excel"
            )
    except Exception as e:
        st.error(f"Error detectado: {e}")

