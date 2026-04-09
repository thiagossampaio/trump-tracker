# Skill: review (Telegram)

Moderação de eventos com score ≥ 8 via Telegram Bot API.
NÃO é um dashboard web — é 100% via Telegram inline keyboards.

## Fluxo
1. classify_agent detecta score ≥ 8
2. telegram_agent envia card formatado para TELEGRAM_CHAT_ID
3. Moderador responde via [✅ Publicar] [❌ Rejeitar]
4. Cloudflare Worker (webhook) recebe callback e atualiza status no banco
5. No próximo run do cron, publish_agent processa os aprovados

## Configuração
TELEGRAM_BOT_TOKEN — via @BotFather
TELEGRAM_CHAT_ID — ID do chat do moderador

## Webhook vs. Polling
SEMPRE webhook em produção. O Cloudflare Worker acorda apenas
quando o moderador responde. Zero custo de compute em idle.