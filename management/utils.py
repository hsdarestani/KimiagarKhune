import json
import re
from urllib import parse as urllib_parse
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from django.conf import settings

PERSIAN_DIGIT_TRANSLATION = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')


def normalize_phone_number(value):
    """Normalize Persian digits and strip unsupported characters from phone numbers."""

    if value is None:
        return ''
    normalized = str(value).strip().translate(PERSIAN_DIGIT_TRANSLATION)
    normalized = re.sub(r'[^0-9+]', '', normalized)
    if normalized.startswith('00'):
        normalized = '+' + normalized[2:]
    if normalized.startswith('0') and len(normalized) == 11:
        normalized = '+98' + normalized[1:]
    return normalized


def send_telegram_message(chat_id: str, text: str):
    token = settings.TELEGRAM_BOT_TOKEN
    proxy_url = getattr(settings, 'TELEGRAM_WORKER_URL', '')
    if not token:
        raise ValueError('TELEGRAM_BOT_TOKEN is not configured.')
    if not proxy_url:
        raise ValueError('TELEGRAM_WORKER_URL is not configured.')

    payload = json.dumps({
        'token': token,
        'chat_id': str(chat_id),
        'text': text,
    }).encode('utf-8')
    req = urllib_request.Request(
        proxy_url,
        data=payload,
        headers={'Content-Type': 'application/json'},
    )

    try:
        with urllib_request.urlopen(req, timeout=15) as response:
            raw_body = response.read().decode('utf-8')
    except (HTTPError, URLError) as exc:
        raise ValueError(f'Telegram proxy request failed: {exc}') from exc

    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise ValueError('Invalid response from telegram proxy.') from exc

    if not body.get('ok'):
        raise ValueError(body.get('description', body.get('error', 'Failed to send telegram notification.')))


def send_sms_message(phone_number: str, text: str):
    api_key = getattr(settings, 'KAVENEGAR_API_KEY', '')
    if not api_key:
        raise ValueError('KAVENEGAR_API_KEY is not configured.')

    normalized = normalize_phone_number(phone_number)
    if not normalized:
        raise ValueError('شماره موبایل نامعتبر است.')

    url = f'https://api.kavenegar.com/v1/{api_key}/sms/send.json'
    payload = {
        'receptor': normalized,
        'message': text,
    }
    sender = getattr(settings, 'KAVENEGAR_SENDER', '')
    if sender:
        payload['sender'] = sender

    data = urllib_parse.urlencode(payload).encode()
    req = urllib_request.Request(url, data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
    with urllib_request.urlopen(req, timeout=10) as response:
        body = json.loads(response.read().decode('utf-8'))

    status_code = body.get('return', {}).get('status')
    if status_code not in (200, 201):
        raise ValueError(body.get('return', {}).get('message', 'Failed to send SMS notification.'))

    return body
