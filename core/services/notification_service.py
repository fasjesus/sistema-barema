# notification_service.py
import os

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client


class NotificationService:
    def __init__(self):
        # Configurações de WhatsApp (Twilio)
        self.wa_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.wa_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.wa_from = os.getenv('TWILIO_WHATSAPP_NUMBER')

        # Configurações de E-mail (SendGrid)
        self.sg_api_key = os.getenv('SENDGRID_API_KEY')
        self.email_from = os.getenv('EMAIL_FROM')

    def enviar_feedback(self, analise, parecer):
        """Método mestre que decide por onde enviar."""
        mensagem = f"Olá {analise.nome_aluno}, seu Barema foi analisado! Parecer: {parecer}"
        resultados = {}

        # Envia email também quando WhatsApp for preferido, como fallback de entrega.
        if analise.email_aluno:
            resultados['email'] = self._enviar_email(analise.email_aluno, mensagem)

        if analise.metodo_preferencial == 'whatsapp':
            numero = self._normalizar_numero_whatsapp(analise.whatsapp_aluno)
            if not numero:
                print(
                    "WhatsApp nao enviado: aluno marcou WhatsApp, "
                    "mas nenhum numero valido foi salvo na analise."
                )
                resultados['whatsapp'] = None
                return resultados

            resultados['whatsapp'] = self._enviar_whatsapp(numero, mensagem)

        return resultados

    def _normalizar_numero_whatsapp(self, numero):
        """Mantém apenas dígitos e garante o DDI do Brasil."""
        digitos = ''.join(char for char in str(numero or '') if char.isdigit())
        if not digitos:
            return None

        if not digitos.startswith('55'):
            digitos = f"55{digitos}"

        return digitos

    def _numero_whatsapp_sem_nono_digito(self, numero):
        if len(numero) == 13 and numero.startswith('55') and numero[4] == '9':
            return f"{numero[:4]}{numero[5:]}"

        return None

    def _enviar_whatsapp(self, para, texto, permitir_fallback=True):
        campos_obrigatorios = {
            'TWILIO_ACCOUNT_SID': self.wa_sid,
            'TWILIO_AUTH_TOKEN': self.wa_token,
            'TWILIO_WHATSAPP_NUMBER': self.wa_from,
        }
        faltando = [nome for nome, valor in campos_obrigatorios.items() if not valor]
        if faltando:
            print(f"WhatsApp nao enviado: configuracao Twilio ausente: {', '.join(faltando)}")
            return None

        try:
            client = Client(self.wa_sid, self.wa_token)
            message = client.messages.create(
                from_=self.wa_from,
                body=texto,
                to=f"whatsapp:+{para}"
            )
            status_message = client.messages(message.sid).fetch()
            print(
                "WhatsApp solicitado via Twilio "
                f"sid={status_message.sid} status={status_message.status} "
                f"error_code={status_message.error_code} "
                f"error_message={status_message.error_message} "
                f"from={self.wa_from} to=whatsapp:+{para}"
            )
            if status_message.error_code == 63015:
                print(
                    "Twilio Sandbox: o destinatario precisa entrar no Sandbox "
                    "enviando a frase 'join ...' exibida no Console da Twilio."
                )
                numero_alternativo = self._numero_whatsapp_sem_nono_digito(para)
                if permitir_fallback and numero_alternativo:
                    print(
                        "Tentando novamente sem o nono digito do celular, "
                        f"pois o Sandbox recebeu join de whatsapp:+{numero_alternativo}."
                    )
                    return self._enviar_whatsapp(numero_alternativo, texto, permitir_fallback=False)

            return status_message
        except TwilioRestException as e:
            print(
                "Erro Twilio ao enviar WhatsApp: "
                f"status={e.status} code={e.code} message={e.msg}"
            )
            if e.code == 63015:
                print(
                    "Twilio Sandbox: o destinatario precisa entrar no Sandbox "
                    "enviando a frase 'join ...' exibida no Console da Twilio."
                )
                numero_alternativo = self._numero_whatsapp_sem_nono_digito(para)
                if permitir_fallback and numero_alternativo:
                    print(
                        "Tentando novamente sem o nono digito do celular, "
                        f"pois o Sandbox pode ter registrado whatsapp:+{numero_alternativo}."
                    )
                    return self._enviar_whatsapp(numero_alternativo, texto, permitir_fallback=False)
        except Exception as e:
            print(f"Erro no WhatsApp: {e}")

        return None

    def _enviar_email(self, para, texto):
        try:
            conteudo_html = f"""
            <div style="font-family: sans-serif; max-width: 600px; border: 1px solid #ddd; border-radius: 10px; padding: 20px;">
                <h2 style="color: #28a745;">Feedback do seu Barema</h2>
                <p>Seu processo de Atividades Complementares foi analisado pelo coordenador.</p>
                <div style="background-color: #f9f9f9; padding: 15px; border-left: 5px solid #ffe45e; margin: 20px 0;">
                    <strong>Acompanhe:</strong><br>
                    {texto}
                </div>
                <p style="font-size: 0.8em; color: #666;">
                    Este é um e-mail automático enviado pelo Sistema de Barema - COLCIC/UESC.
                </p>
            </div>
            """

            message = Mail(
                from_email=self.email_from,
                to_emails=para,
                subject='Parecer de Atividades Complementares - UESC',
                html_content=conteudo_html
            )
            sg = SendGridAPIClient(self.sg_api_key)
            response = sg.send(message)
            print(f"E-mail enviado com sucesso para {para} status={response.status_code}")
            return response
        except Exception as e:
            print(f"Erro ao enviar e-mail: {e}")
            return None
