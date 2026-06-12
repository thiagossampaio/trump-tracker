/**
 * telegram-webhook.js
 * --------------------
 * Cloudflare Worker — recebe callbacks do Telegram (inline keyboard)
 * e atualiza o status do artigo no Supabase.
 *
 * Fluxo:
 *   1. Telegram envia POST com callback_query ao receber clique no botão
 *   2. Extrai action ("publish" ou "reject") e article_id do callback_data
 *   3. Atualiza raw_articles.status no Supabase via REST API
 *   4. Responde ao Telegram com answerCallbackQuery (confirmação visual)
 *   5. Retorna 200 em todos os casos (evita retentativas do Telegram)
 *
 * Secrets necessários (wrangler secret put):
 *   SUPABASE_URL, SUPABASE_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET
 *
 * O TELEGRAM_WEBHOOK_SECRET deve ser o mesmo passado em setWebhook
 * (secret_token) — o Telegram o envia no header
 * X-Telegram-Bot-Api-Secret-Token e validamos aqui para impedir que
 * terceiros forjem aprovações conhecendo a URL do worker.
 */

export default {
  async fetch(request, env) {
    // Telegram só envia POST — qualquer outra coisa retorna 200 silenciosamente
    if (request.method !== "POST") {
      return new Response("OK", { status: 200 });
    }

    // Valida o secret do webhook (anti-forgery)
    const secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
    if (!env.TELEGRAM_WEBHOOK_SECRET || secret !== env.TELEGRAM_WEBHOOK_SECRET) {
      return new Response("Forbidden", { status: 403 });
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return new Response("OK", { status: 200 });
    }

    const query = body?.callback_query;
    if (!query) {
      // Pode ser um update de mensagem normal — ignorar
      return new Response("OK", { status: 200 });
    }

    const callbackData = query.data ?? "";
    const colonIdx = callbackData.indexOf(":");
    if (colonIdx === -1) {
      await answerCallback(env, query.id, "⚠️ Formato inválido");
      return new Response("OK", { status: 200 });
    }

    const action = callbackData.slice(0, colonIdx);
    const articleId = callbackData.slice(colonIdx + 1);

    if (!articleId) {
      await answerCallback(env, query.id, "⚠️ ID inválido");
      return new Response("OK", { status: 200 });
    }

    if (action !== "publish" && action !== "reject") {
      await answerCallback(env, query.id, "⚠️ Ação desconhecida");
      return new Response("OK", { status: 200 });
    }

    const newStatus = action === "publish" ? "approved_manual" : "rejected";
    const label = action === "publish" ? "✅ Aprovado para publicação" : "❌ Rejeitado";

    await Promise.all([
      updateSupabase(env, articleId, newStatus),
      answerCallback(env, query.id, label),
      // Remove os botões e registra o veredito no card (evita duplo clique)
      finalizeMessage(env, query, label),
    ]);

    return new Response("OK", { status: 200 });
  },
};

/**
 * Edita a mensagem original: remove o teclado inline e anexa o veredito.
 */
async function finalizeMessage(env, query, label) {
  const message = query.message;
  if (!message) return;

  const url = `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageText`;
  const reviewer = query.from?.first_name || query.from?.username || "revisor";
  try {
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: message.chat.id,
        message_id: message.message_id,
        text: `${message.text}\n\n━━━━━━━━━━\n${label} por ${reviewer}`,
        // sem reply_markup → teclado removido
      }),
    });
  } catch (err) {
    console.error(`editMessageText falhou: ${err}`);
  }
}

/**
 * Atualiza raw_articles.status via Supabase REST API.
 */
async function updateSupabase(env, articleId, newStatus) {
  const url = `${env.SUPABASE_URL}/rest/v1/raw_articles?id=eq.${encodeURIComponent(articleId)}`;
  try {
    await fetch(url, {
      method: "PATCH",
      headers: {
        apikey: env.SUPABASE_KEY,
        Authorization: `Bearer ${env.SUPABASE_KEY}`,
        "Content-Type": "application/json",
        Prefer: "return=minimal",
      },
      body: JSON.stringify({ status: newStatus }),
    });
  } catch (err) {
    console.error(`Supabase PATCH falhou para ${articleId}: ${err}`);
  }
}

/**
 * Envia answerCallbackQuery ao Telegram para exibir feedback visual ao usuário.
 */
async function answerCallback(env, callbackQueryId, text) {
  const url = `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`;
  try {
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        callback_query_id: callbackQueryId,
        text,
        show_alert: false,
      }),
    });
  } catch (err) {
    console.error(`answerCallbackQuery falhou: ${err}`);
  }
}
