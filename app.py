import streamlit as st
import pandas as pd
import pdfplumber
import re
import io

st.set_page_config(page_title="Extractor F.931 Definitivo", layout="wide")
st.title("📑 Consolidador Multiempresa F.931")

def limpiar_monto(texto):
    """Convierte texto de moneda ($ 1.234,56) a float (1234.56)"""
    if not texto: return 0.0
    try:
        # Eliminar todo lo que no sea número, coma o punto
        limpio = re.sub(r'[^\d,.-]', '', texto)
        if not limpio: return 0.0
        
        # Lógica para detectar miles y decimales formato Argentina
        if ',' in limpio and '.' in limpio:
            # Tiene ambos (ej: 1.234,56) -> eliminar punto, cambiar coma por punto
            limpio = limpio.replace('.', '').replace(',', '.')
        elif ',' in limpio:
            # Solo tiene coma (ej: 1234,56) -> cambiar por punto
            limpio = limpio.replace(',', '.')
        # Si solo tiene punto (ej: 1.234), asumimos que es miles si son 3 digitos, o error.
        # Para 931 estándar, la coma es el decimal.
        
        return float(limpio)
    except:
        return 0.0

def extraer_valor_linea(linea):
    """Busca todos los montos en una línea y devuelve el mayor (evita los 0.00 de tasas)"""
    # Busca patrones numéricos tipo 1.234,56 o 1234,56
    coincidencias = re.findall(r'[\d.]+,\d{2}', linea)
    montos = [limpiar_monto(m) for m in coincidencias]
    
    # Filtramos ceros y nos quedamos con el máximo valor encontrado en esa línea
    montos_validos = [m for m in montos if m > 0]
    
    if montos_validos:
        return max(montos_validos) # Devuelve el importe más grande (el total)
    return 0.0

def procesar_931(file):
    with pdfplumber.open(file) as pdf:
        # Extraemos texto página por página manteniendo la estructura física
        full_text = ""
        for page in pdf.pages:
            full_text += page.extract_text() + "\n"
        
        lines = full_text.split('\n')
        res = {}
        
        # Inicializamos variables en 0
        campos = [
            'Rem 1', 'Rem 4', 'Rem 8', 'Rem 9', 'Rem 10', 
            'Ley 27430 Detraido', 'Dec 394', 
            '351-Contrib SS', '351-SIPA', '351-No SIPA', '301-Aportes SS',
            '352-Contrib OS', '302-Aportes OS', '312-LRT', '028-Vida'
        ]
        for c in campos: res[c] = 0.0

        # --- EXTRACCIÓN LÍNEA POR LÍNEA (Más segura) ---
        for line in lines:
            line_upper = line.upper()

            # Identificación
            if "RAZON SOCIAL" in line_upper or "APELLIDO Y NOMBRE" in line_upper:
                res['Empresa'] = line.split(':')[-1].strip()
            if "CUIT" in line_upper and "PERIOD" not in line_upper:
                match = re.search(r'\d{2}-\d{8}-\d', line)
                if match: res['CUIT'] = match.group(0)
            if "PERIODO" in line_upper or "PERÍODO" in line_upper:
                match = re.search(r'\d{2}/\d{4}', line)
                if match: res['Mes - Año'] = match.group(0)
            if "NOMINA" in line_upper or "EMPLEADOS" in line_upper:
                match = re.search(r'\d+', line.split(':')[-1])
                if match: res['Empleados'] = match.group(0)

            # Remuneraciones
            for r in [1, 4, 8, 9, 10]:
                if f"REM. {r}" in line_upper or f"REMUNERACION {r}" in line_upper or f"REM {r} " in line_upper:
                     # Para remuneraciones, a veces el numero está pegado al texto, usamos regex específico
                     val = extraer_valor_linea(line)
                     if val > 0: res[f'Rem {r}'] = val

            # Detracciones
            if "DETRAIDO" in line_upper:
                res['Ley 27430 Detraido'] = extraer_valor_linea(line)
            if "DECRETO 394" in line_upper or "DEC 394" in line_upper or "DEC. 394" in line_upper:
                res['Dec 394'] = extraer_valor_linea(line)

            # Conceptos de Seguridad Social y Obra Social
            # Usamos códigos específicos para evitar confusiones
            
            # 351 Total
            if "351" in line and "CONTRIBUCIONES" in line_upper and "SEGURIDAD" in line_upper:
                res['351-Contrib SS'] = extraer_valor_linea(line)
            
            # SIPA y No SIPA (A veces comparten linea o estan cerca, mejor buscar especifico)
            elif "SIPA" in line_upper and "NO SIPA" not in line_upper and "CONTRIBUCIONES" in line_upper: # Solo SIPA
                 # A veces dice "Regimen Nacional...", buscamos la linea que tenga plata
                 val = extraer_valor_linea(line)
                 if val > 0 and res['351-SIPA'] == 0: res['351-SIPA'] = val
            
            elif "NO SIPA" in line_upper:
                 val = extraer_valor_linea(line)
                 if val > 0: res['351-No SIPA'] = val

            # 301 Aportes
            if "301" in line and "APORTES" in line_upper:
                res['301-Aportes SS'] = extraer_valor_linea(line)

            # 352 OS
            if "352" in line and "CONTRIBUCIONES" in line_upper:
                res['352-Contrib OS'] = extraer_valor_linea(line)
            
            # 302 Aportes OS
            if "302" in line and "APORTES" in line_upper:
                res['302-Aportes OS'] = extraer_valor_linea(line)
            
            # LRT
            if "312" in line or ("LRT" in line_upper and "LEY" in line_upper):
                val = extraer_valor_linea(line)
                if val > 0: res['312-LRT'] = val
            
            # Vida
            if "028" in line or "VIDA OBLIGATORIO" in line_upper:
                res['028-Vida'] = extraer_valor_linea(line)

        # Valores por defecto si no encontró identificación
        if 'Empresa' not in res: res['Empresa'] = "No Identificada"
        if 'Mes - Año' not in res: res['Mes - Año'] = "S/D"

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
            
            # Filtrar y trasponer
            df_final = df[df['Empresa'] == emp_sel].set_index('Mes - Año').T
            
            st.write(f"### Planilla: {emp_sel}")
            st.dataframe(df_final) # Sin formato forzado para evitar errores
            
            # Excel
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_final.to_excel(writer, sheet_name='F931')
            
            st.download_button("📥 Descargar Excel", buffer.getvalue(), f"931_{emp_sel}.xlsx")
            
    except Exception as e:
        st.error(f"Error: {e}")

