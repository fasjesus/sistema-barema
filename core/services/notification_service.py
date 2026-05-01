import os
from twilio.rest import Client
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

class NotificationService:
    def __init__(self):
        # Configurações de WhatsApp (Twilio)
        self.wa_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.wa_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.wa_from = os.getenv('TWILIO_WHATSAPP_NUMBER')
        
        # Configurações de E-mail (SendGrid)
        self.sg_api_key = os.getenv('SENDGRID_API_KEY')
        self.email_from = os.getenv('EMAIL_FROM') # Seu e-mail verificado no SendGrid

    def enviar_feedback(self, analise, parecer):
        """Método mestre que decide por onde enviar"""
        mensagem = f"Olá {analise.nome_aluno}, seu Barema foi analisado! Parecer: {parecer}"

        '''Envia email também mesmo que o método seja WhatsApp, para garantir que o aluno receba a mensagem de alguma forma.'''
        if analise.email_aluno:
            self._enviar_email(analise.email_aluno, mensagem)

        if analise.metodo_preferencial == 'whatsapp':
            numero = analise.whatsapp_aluno
            if not numero.startswith('55'):
                numero = f"55{numero}"
            return self._enviar_whatsapp(numero, mensagem)


    def _enviar_whatsapp(self, para, texto):
        try:
            client = Client(self.wa_sid, self.wa_token)
            client.messages.create(
                from_=self.wa_from,
                body=texto,
                to=f"whatsapp:+{para}"
            )
            print(f"WhatsApp enviado para {para}")
        except Exception as e:
            print(f"Erro no WhatsApp: {e}")

    def _enviar_email(self, para, texto):
        try:
            # HTML básico com estilo CSS inline 
            conteudo_html = f"""
            <div style="font-family: sans-serif; max-width: 600px; border: 1px solid #ddd; border-radius: 10px; padding: 20px;">
                <h2 style="color: #28a745;">Feedback do seu Barema</h2>
                <p>Olá, o seu processo de Atividades Complementares foi analisado pelo coordenador.</p>
                <div style="background-color: #f9f9f9; padding: 15px; border-left: 5px solid #ffe45e; margin: 20px 0;">
                    <strong>Parecer da Coordenação:</strong><br>
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
                html_content=conteudo_html # Agora enviamos HTML em vez de texto puro
            )
            sg = SendGridAPIClient(self.sg_api_key)
            sg.send(message)
            print(f"📧 E-mail enviado com sucesso para {para}")
        except Exception as e:
            print(f"❌ Erro ao enviar e-mail: {e}")