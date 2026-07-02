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
        mensagem = f"Olá {analise.nome_aluno}, seu Barema foi analisado!\nParecer: {parecer}"
        mensagem_email = f"Olá {analise.nome_aluno}, seu Barema foi analisado!<br><strong>Parecer:</strong> {parecer}"
        resultados = {}

        # Envia email também quando WhatsApp for preferido, como fallback de entrega.
        if analise.email_aluno:
            resultados['email'] = self._enviar_email(analise.email_aluno, mensagem_email)

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
            <div style="width: 100%; margin: 0; padding: 32px 0; background-color: #e8f1ff; text-align: center;">
                <div style="width: 100%; max-width: 620px; margin: 0 auto; font-family: Arial, Helvetica, sans-serif; color: #232323; text-align: left;">
                    <div style="background-color: #314ca5; border-radius: 10px 10px 0 0; padding: 24px 28px; border-bottom: 5px solid #ffe45e;">
                        <p style="margin: 0 0 8px 0; color: #ffe45e; font-size: 13px; font-weight: 700; letter-spacing: 0.02em; text-transform: uppercase;">
                            Sistema de Barema - COLCIC/UESC
                        </p>
                        <h2 style="margin: 0; color: #ffffff; font-size: 24px; line-height: 1.3;">
                            Feedback do seu Barema
                        </h2>
                    </div>

                    <div style="background-color: #ffffff; border: 1px solid #d4e1f4; border-top: 0; border-radius: 0 0 10px 10px; padding: 28px; box-shadow: 0 10px 24px rgba(49, 76, 165, 0.12);">
                        <p style="margin: 0; color: #333333; font-size: 16px; line-height: 1.6;">
                            Seu processo de Atividades Complementares foi analisado pelo coordenador.
                        </p>

                        <div style="background-color: #f4f7ff; border-left: 6px solid #ffe45e; border-radius: 6px; margin: 24px 0; padding: 18px 20px;">
                            <strong style="display: block; margin-bottom: 8px; color: #283a73; font-size: 16px;">
                                Acompanhe:
                            </strong>
                            <div style="color: #333333; font-size: 15px; line-height: 1.6;">
                                {texto}
                            </div>
                        </div>

                        <p style="margin: 0; padding-top: 18px; border-top: 1px solid #d4e1f4; color: #666666; font-size: 13px; line-height: 1.5;">
                            Este é um e-mail automático enviado pelo Sistema de Barema - COLCIC/UESC.
                        </p>
                    </div>
                </div>
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
