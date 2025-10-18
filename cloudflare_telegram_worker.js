// Cloudflare Worker script that proxies Telegram bot requests.
// Deploy this worker and update TELEGRAM_WORKER_URL in Django settings to point to it.
// Store your bot token securely as an environment variable named TELEGRAM_BOT_TOKEN,
// or provide it in the JSON payload alongside chat_id and text.

export default {
  async fetch(request, env, ctx) {
    if (request.method !== 'POST') {
      return new Response(JSON.stringify({
        ok: false,
        description: 'Only POST requests are supported.'
      }), {
        status: 405,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
        },
      });
    }

    let payload;
    try {
      payload = await request.json();
    } catch (err) {
      return new Response(JSON.stringify({
        ok: false,
        description: 'Invalid JSON payload.',
      }), {
        status: 400,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
        },
      });
    }

    const token = payload.token || env.TELEGRAM_BOT_TOKEN;
    const chatId = payload.chat_id;
    const text = payload.text;

    if (!token) {
      return new Response(JSON.stringify({
        ok: false,
        description: 'Telegram bot token is missing.',
      }), {
        status: 400,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
        },
      });
    }

    if (!chatId || !text) {
      return new Response(JSON.stringify({
        ok: false,
        description: 'Both chat_id and text must be provided.',
      }), {
        status: 400,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
        },
      });
    }

    const telegramResponse = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        chat_id: chatId,
        text,
      }),
    });

    const resultBody = await telegramResponse.text();

    return new Response(resultBody, {
      status: telegramResponse.status,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
      },
    });
  },
};
