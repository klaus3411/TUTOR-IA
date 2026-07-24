import os
import mercadopago
import streamlit as st

def crear_link_de_pago(estudiante_email, monto=80000, plan_nombre="Suscripción Tutor IA - NOVA"):
    """
    Genera una preferencia de pago en Mercado Pago por $80.000 COP.
    """
    sdk = mercadopago.SDK(os.getenv("MERCADOPAGO_ACCESS_TOKEN"))

    preference_data = {
        "items": [
            {
                "title": plan_nombre,
                "quantity": 1,
                "currency_id": "COP",
                "unit_price": float(monto) # $80.000 COP
            }
        ],
        "payer": {
            "email": estudiante_email
        },
        "back_urls": {
            "success": "https://tutor-ia-6sfonzsurtvkg9cfd4ecag.streamlit.app/?pago=exitoso",
            "failure": "https://tutor-ia-6sfonzsurtvkg9cfd4ecag.streamlit.app/?pago=fallido",
            "pending": "https://tutor-ia-6sfonzsurtvkg9cfd4ecag.streamlit.app/?pago=pendiente"
        },
        "auto_return": "approved",
    }

    preference_response = sdk.preference().create(preference_data)
    return preference_response["response"]["init_point"]

# --- INTERFAZ EN STREAMLIT ---
def mostrar_interfaz_pago():
    st.title("💳 Inscripción al Tutor IA - NOVA")
    st.write("Plan Personalizado Premium: **$80.000 COP / mes**")
    
    email = st.text_input("Ingresa el correo del estudiante:")
    
    if st.button("Proceder al Pago"):
        if email:
            try:
                url_pago = crear_link_de_pago(estudiante_email=email)
                st.success("¡Enlace de pago generado con éxito!")
                st.link_button("👉 Ir a Pagar Ahora (PSE, Nequi, Tarjeta)", url_pago)
            except Exception as e:
                st.error(f"Error al conectar con la pasarela: {e}")
        else:
            st.warning("Por favor ingresa un correo válido.")