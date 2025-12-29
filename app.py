import streamlit as st
import pandas as pd
import pdfplumber
import re
import io

st.set_page_config(page_title="Extractor F.931 Contable", layout="wide")
st.title("📑 Consolidador F.931 - Sección VIII")

def limpiar_monto(texto):
    """Convierte texto ($ 649.976,20) a float (649976.20)"""
    if not texto: return 0.0
    try:
        # Dejar solo números, comas y puntos
        limpio = re.sub(r'[^\d,.-]', '', texto)
        if not limpio: return 0.0
        
        # Lógica Argentina: si hay punto y coma, el punto vuela y la coma es decimal
        if ',' in limpio and '.' in limpio:
            limpio = limpio.replace('.', '').replace(',', '.')
        elif ',' in limpio:
            limpio = limpio.replace(',', '.')
        
        return float(limpio)
    except:
        return 0.0

def procesar_931(file, index):
    with pdfplumber.open(file) as pdf:
        # Extraer todo el texto junto
        txt = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        
        res = {}
        
        # --- 1. IDENTIFICACIÓN (Razón Social y CUIT) ---
        # Busca Razón social arriba de todo
        rs = re.search(r"(?:Social|Razon Social):\s*\n?\s*(.*)", txt, re.IGNORECASE)
        res['Empresa'] = rs.group(1).strip() if rs else "Empresa No Identificada"
        
        cuit = re.search(r"\b(20|23|27|30|33)-\d{8}-\d\b", txt)
        res['CUIT'] = cuit.group(0) if cuit else "S/D"
        
        # --- 2. FECHA (Para evitar error de columnas duplicadas) ---
        # Primero busca en el texto
        per_match = re.search(r"(\d{2}/\d{4})", txt)
        if per_match:
            res['Mes - Año'] = per_match.group(1)
        else:
            # Si no encuentra en el texto, busca en el nombre del archivo (ej: 01-2025.pdf)
            name_match = re.search(r"(\d{2}[-.]\d{4})", file.name)
            if name_match:
                res['Mes - Año'] = name_match.group(1).replace('-', '/').replace('.', '/')
            else:
                # Si falla todo, usa un nombre genérico para que NO se rompa la app
                res['Mes - Año'] = f"Archivo {index+1}"

        # --- 3. EXTRACCIÓN ESPECÍFICA (Basada en tu Imagen) ---
        
        # A. Remuneraciones (Busca Rem. X seguido de un monto)
        for r in [1, 4, 8, 9, 10]:
            # Regex busca "Rem. 1" ...espacio... numero
            match = re.search(rf"Rem\. {r}.*?([\d.,]+)", txt)
            res[f'Rem {r}'] = limpiar_monto(match.group(1)) if match else 0.0

        # B. Ley 27430 (Monto Total Detraído)
        # En tu imagen dice: "Ley 27.430 - Monto Total Detraido: 28.014,72"
        detraido = re.search(r"Ley 27\.430.*?Detraido[:\s]+([\d.,]+)", txt, re.IGNORECASE)
        res['Ley 27430 Detraido'] = limpiar_monto(detraido.group(1)) if detraido else 0.0

        # C. SECCIÓN VIII - MONTOS QUE SE INGRESAN (Los códigos de tu imagen)
        # Usamos re.DOTALL para que busque saltos de linea si es necesario
        
        # 351
        m351 = re.search(r"351\s*-\s*Contribuciones.*?Seguridad Social\s+([\d.,]+)", txt, re.IGNORECASE)
        res['351-Contrib SS'] = limpiar_monto(m351.group(1)) if m351 else 0.0
        
        # 301
        m301 = re.search(r"301\s*-\s*Aportes.*?Seguridad Social\s+([\d.,]+)", txt, re.IGNORECASE)
        res['301-Aportes SS'] = limpiar_monto(m301.group(1)) if m301 else 0.0
        
        # 352
        m352 = re.search(r"352\s*-\s*Contribuciones.*?Obra Social\s+([\d.,]+)", txt, re.IGNORECASE)
        res['352-Contrib OS'] = limpiar_monto(m352.group(1)) if m352 else 0.0
        
        # 302
        m302 = re.search(r"302\s*-\s*Aportes.*?Obra Social\s+([\d.,]+)", txt, re.IGNORECASE)
        res['302-Aportes OS'] = limpiar_monto(m302.group(1)) if m302 else 0.0
        
        # 312 (LRT)
        m312 = re.search(r"312\s*-\s*L\.?R\.?T\.?\s+([\d.,]+)", txt, re.IGNORECASE)
        res['312-LRT'] = limpiar_monto(m312.group(1)) if m312 else 0.0
        
        # 028 (Vida)
        m028 = re.search(r"(?:028|SCVO)\s*-\s*Seguro.*?Vida.*?\s+([\d.,]+)", txt, re.IGNORECASE)
        res['028-Vida'] = limpiar_monto(m028.group(1)) if m028 else 0.0

        return res

# --- INTERFAZ ---
files = st.file_uploader("Cargá tus F.931 (PDF)", type="pdf", accept_multiple_files=True)

if files:
    try:
        data = []
        # Pasamos el índice (i) para usarlo de respaldo si falta la fecha
        for i, f in enumerate(files):
            data.append(procesar_931(f, i))
            
        df = pd.DataFrame(data)
        
        if not df.empty:
            # Seleccionamos empresa
            empresas = df['Empresa'].unique()
            emp_sel = st.selectbox("Empresa:", empresas)
            
            # Filtramos
            df_final = df[df['Empresa'] == emp_sel].copy()
            
            # Validamos que no haya duplicados en la columna de fecha
            if df_final['Mes - Año'].duplicated().any():
                st.warning("⚠️ Hay archivos con la misma fecha. Se agregarán sufijos para no perder datos.")
                # Truco para hacer únicos los nombres de columnas
                df_final['Mes - Año'] = df_final['Mes - Año'] + df_final.groupby('Mes - Año').cumcount().astype(str).replace('0', '')
            
            # Pivotamos la tabla
            df_pivot = df_final.set_index('Mes - Año').T
            
            st.success(f"✅ Datos extraídos de la Sección VIII para {emp_sel}")
            st.dataframe(df_pivot)
            
            # Excel
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_pivot.to_excel(writer, sheet_name='F931_Datos')
            st.download_button("📥 Descargar Excel", buffer.getvalue(), f"931_{emp_sel[:5]}.xlsx")
            
    except Exception as e:
        st.error(f"Error: {e}")
