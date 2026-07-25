# Contenido completo de pagos.py
import os
import mercadopago
import streamlit as st

def crear_link_de_pago(estudiante_email, monto=80000, plan_nombre="Suscripción Tutor IA - NOVA"):
    token = st.secrets.get("MERCADOPAGO_ACCESS_TOKEN", os.getenv("MERCADOPAGO_ACCESS_TOKEN"))
    sdk = mercadopago.SDK(token)

    preference_data = {
        "items": [{
            "title": plan_nombre,
            "quantity": 1,
            "currency_id": "COP",
            "unit_price": float(monto)
        }],
        "payer": {"email": estudiante_email},
        "back_urls": {
            "success": "https://tu-app.streamlit.app/?pago=exitoso",
            "failure": "https://tu-app.streamlit.app/?pago=fallido",
            "pending": "https://tu-app.streamlit.app/?pago=pendiente"
        },
        "auto_return": "approved",
    }

    preference_response = sdk.preference().create(preference_data)
    return preference_response["response"]["init_point"]

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