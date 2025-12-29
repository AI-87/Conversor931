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
        # Extrae solo dígitos, comas y puntos (y signo negativo)
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
        
        # Razón social (línea después de "Apellido y Nombre o Razón Social:")
        rs = re.search(r"Raz[oó]n Social:\s*\n?\s*(.*)", txt)
        res['Empresa'] = rs.group(1).strip() if rs else "Empresa No Identificada"
        
        # CUIT
        cuit = re.search(r"(\d{2}-\d{8}-\d)", txt)
        res['CUIT'] = cuit.group(1) if cuit else "S/D"
        
        # Mes - Año (ej: 11/2025)
        per = re.search(r"Mes\s*-\s*A[oó]\s*(\d{2}/\d{4})", txt, re.I)
        res['Mes - Año'] = per.group(1) if per else "S/D"
        
        # Empleados en nómina
        emp = re.search(r"Empleados en n[oó]mina:\s*(\d+)", txt, re.I)
        res['Empleados'] = emp.group(1) if emp else "0"

        # Remuneraciones (1, 4, 8, 9, 10)
        for r in [1, 4, 8, 9, 10]:
            m = re.search(rf"Suma de Rem\. {r}:\s*([\d.,]+)", txt)
            res[f"Rem {r}"] = limpiar_monto(m.group(1)) if m else 0.0

        # Ley 27.430 Monto Total Detraído
        det = re.search(r"Ley\s*27\.?430.*?Detra[ií]do[:\s]+([\d.,]+)", txt, re.I)
        res["Ley 27430 Detraido"] = limpiar_monto(det.group(1)) if det else 0.0

        # Pago a Cuenta Dec. 394
        dec = re.search(r"Pago a Cuenta\s*Dec\.?\s*394[:\s]+([\d.,]+)", txt, re.I)
        res["Dec 394"] = limpiar_monto(dec.group(1)) if dec else 0.0

        # --- Conceptos AFIP (bloque VIII - MONTOS QUE SE INGRESAN) ---
        patrones = {
            "351-Contrib SS Total": r"351\s*-\s*Contribuciones de Seguridad Social\s+([\d.,]+)",
            "351-SIPA": r"351\s+Contribuciones S\.?S\.?\s*SIPA\s+([\d.,]+)",
            "351-No SIPA": r"351\s+Contribuciones S\.?S\.?\s*No\s+SIPA\s+([\d.,]+)",
            "301-Aportes SS": r"301\s*-\s*Aportes de Seguridad Social\s+([\d.,]+)",
            "352-Contrib OS": r"352\s+Contribuciones de Obra Social\s+([\d.,]+)",
            "302-Aportes OS": r"302\s*-\s*Aportes de Obra Social\s+([\d.,]+)",
            "312-LRT": r"312\s*-\s*L\.?R\.?T\.?\s+([\d.,]+)",
            "028-Vida": r"028\s*-\s*Seguro Colectivo de Vida Obligatorio\s+([\d.,]+)",
        }

        for clave, regex in patrones.items():
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
            # descarto períodos sin identificar para evitar 'S/D' duplicados
            df = df[df["Mes - Año"] != "S/D"]

            if df.empty:
                st.warning("No se pudo identificar el período (Mes - Año) en los PDF.")
            else:
                empresas = df["Empresa"].unique()
                emp_sel = st.selectbox(
                    "Seleccioná la empresa para generar la planilla:", empresas
                )

                # filtro por empresa y traspongo
                df_emp = df[df["Empresa"] == emp_sel].drop_duplicates(subset=["Mes - Año"])
                df_final = df_emp.set_index("Mes - Año").T

                st.write(f"### Planilla Consolidada: {emp_sel}")
                st.dataframe(df_final)

                # Excel
                buffer = io.BytesIO()
                df_final.to_excel(buffer, sheet_name="Consolidado_931")
                st.download_button(
                    "📥 Descargar Excel",
                    buffer.getvalue(),
                    f"931_{emp_sel}.xlsx",
                )
    except Exception as e:
        st.error(f"Error de procesamiento: {e}")

