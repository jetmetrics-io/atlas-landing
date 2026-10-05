#!/usr/bin/env python3
"""Выложить лендинг Атласа в бой: index.html → бакет jetmetrics-static, ключ landing/atlas/index.html.

    python3 deploy.py --dry-run     # что уедет и чем отличается от боя, без заливки
    python3 deploy.py               # залить

Страница /atlas на Тильде встраивает этот файл iframe'ом (код блока — site-state/tilda/atlas.html),
поэтому после заливки в Тильду заходить не нужно: новая версия видна через 5 минут (max-age=300).

Ключи — сервисный аккаунт static-deploy: YC_KEY_ID и YC_SECRET в окружении или в .deploy.env
рядом с этим файлом (в git не попадает). Нужен boto3.

Перед заливкой скрипт сохраняет боевую версию в .rollback/index.html. Откат:

    python3 deploy.py --rollback
"""
import os, sys, pathlib, urllib.request

PAPKA    = pathlib.Path(__file__).resolve().parent
ENDPOINT = "https://storage.yandexcloud.net"
REGION   = "ru-central1"
BUCKET   = "jetmetrics-static"
KLYUCH   = "landing/atlas/index.html"
BOY      = f"{ENDPOINT}/{BUCKET}/{KLYUCH}"


def load_env():
    f = PAPKA / ".deploy.env"
    if f.exists():
        for line in f.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def client():
    import boto3
    kid, sec = os.environ.get("YC_KEY_ID"), os.environ.get("YC_SECRET")
    if not kid or not sec:
        sys.exit("✖ Нет ключей: YC_KEY_ID / YC_SECRET в окружении или в .deploy.env")
    return boto3.client("s3", endpoint_url=ENDPOINT, region_name=REGION,
                        aws_access_key_id=kid, aws_secret_access_key=sec)


def zalit(cl, telo):
    # ACL обязателен: у бакета нет публичной политики, объект без public-read отдаёт 403.
    # 05.10.2026 первая заливка ушла без него, и лендинг две минуты был недоступен.
    cl.put_object(Bucket=BUCKET, Key=KLYUCH, Body=telo, ACL="public-read",
                  ContentType="text/html; charset=utf-8", CacheControl="max-age=300")


def main():
    load_env()
    args = set(sys.argv[1:])
    boy = urllib.request.urlopen(BOY, timeout=30).read()
    if "--rollback" in args:
        staroe = (PAPKA / ".rollback" / "index.html").read_bytes()
        zalit(client(), staroe)
        print(f"✓ Откат: в бою снова версия из .rollback ({len(staroe):,} байт)".replace(",", " "))
        return
    novoe = (PAPKA / "index.html").read_bytes()
    print(f"бой {len(boy):,} байт · у нас {len(novoe):,} байт".replace(",", " "))
    if boy == novoe:
        print("Отличий нет — заливать нечего.")
        return
    if "--dry-run" in args:
        print("(dry-run) отличается от боя, заливка не выполнялась")
        return
    (PAPKA / ".rollback").mkdir(exist_ok=True)
    (PAPKA / ".rollback" / "index.html").write_bytes(boy)
    zalit(client(), novoe)
    # Проверка: бой отдаёт ровно залитое. Если ACL не встал, здесь будет 403.
    try:
        proverka = urllib.request.urlopen(BOY, timeout=30).read()
    except Exception as e:
        sys.exit(f"⛔ Бой не отдаёт лендинг ({e}). Откат: python3 deploy.py --rollback")
    print("✓ Залито, бой отдаёт новую версию" if proverka == novoe else "⚠ Бой отдаёт не то, что залили — проверь")
    print("   откат, если что: python3 deploy.py --rollback")


if __name__ == "__main__":
    main()
