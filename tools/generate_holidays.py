"""Generate data/holidays/holidays.json from the vendored upstream data.

Holiday dates come from @jalali-js/holidays 0.4.2 (MIT), whose lunar tables
are derived from the University of Tehran Calendar Centre / official Iranian
holiday list.  Non-holiday occasions are a curated subset of
persian-holidays 1.6.1 (MIT).

Usage:
    python tools/generate_holidays.py

Input : tools/upstream/jalali_js_holidays_0.4.2.json
Output: data/holidays/holidays.json
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "tools" / "upstream" / "jalali_js_holidays_0.4.2.json"
OUT = ROOT / "data" / "holidays" / "holidays.json"

HOLIDAY_META = {
    "nowruz": ("نوروز", "national", "آغاز سال نو و جشن باستانی نوروز."),
    "jomhoori-eslami": ("روز جمهوری اسلامی", "national", "سالروز برگزاری همه‌پرسی نظام جمهوری اسلامی."),
    "sizdah-bedar": ("روز طبیعت", "national", "سیزده‌بدر و روز طبیعت."),
    "khomeini-demise": ("رحلت امام خمینی", "national", "سالروز رحلت بنیان‌گذار جمهوری اسلامی ایران."),
    "khordad-15": ("قیام ۱۵ خرداد", "national", "سالروز قیام ۱۵ خرداد ۱۳۴۲."),
    "revolution-day": ("پیروزی انقلاب اسلامی", "national", "سالروز پیروزی انقلاب اسلامی ایران."),
    "oil-nationalization": ("ملی شدن صنعت نفت", "national", "سالروز ملی شدن صنعت نفت ایران."),
    "eyd-fetr": ("عید فطر", "religious", "عید فطر و پایان ماه مبارک رمضان."),
    "eyd-fetr-holiday": ("تعطیل عید فطر", "religious", "تعطیل رسمی به مناسبت عید فطر."),
    "martyrdom-imam-ali": ("شهادت امام علی (ع)", "religious", "سالروز شهادت امام علی (ع)."),
    "martyrdom-imam-sadegh": ("شهادت امام جعفر صادق (ع)", "religious", "سالروز شهادت امام جعفر صادق (ع)."),
    "eyd-qorban": ("عید قربان", "religious", "عید قربان."),
    "eyd-ghadir": ("عید غدیر خم", "religious", "عید غدیر خم."),
    "tasua": ("تاسوعای حسینی", "religious", "تاسوعای حسینی."),
    "ashura": ("عاشورای حسینی", "religious", "عاشورای حسینی."),
    "arbain": ("اربعین حسینی", "religious", "اربعین حسینی."),
    "demise-prophet": ("رحلت پیامبر و شهادت امام حسن (ع)", "religious", "رحلت پیامبر اکرم (ص) و شهادت امام حسن (ع)."),
    "martyrdom-imam-reza": ("شهادت امام رضا (ع)", "religious", "سالروز شهادت امام رضا (ع)."),
    "martyrdom-imam-askari": ("شهادت امام حسن عسکری (ع)", "religious", "سالروز شهادت امام حسن عسکری (ع)."),
    "birth-prophet": ("ولادت پیامبر و امام جعفر صادق (ع)", "religious", "ولادت پیامبر اکرم (ص) و امام جعفر صادق (ع)."),
    "martyrdom-fatemeh": ("شهادت حضرت فاطمه (س)", "religious", "سالروز شهادت حضرت فاطمه (س)."),
    "birth-imam-ali": ("ولادت امام علی (ع)", "religious", "سالروز ولادت امام علی (ع)."),
    "mabas": ("مبعث پیامبر (ص)", "religious", "سالروز مبعث پیامبر اکرم (ص)."),
    "birth-imam-mahdi": ("ولادت حضرت قائم (عج)", "religious", "سالروز ولادت حضرت قائم (عج)."),
}

# Curated, well-known fixed (solar) occasions.  Titles are taken from
# persian-holidays 1.6.1; categories and descriptions are ours.
OCCASIONS = [
    (1, 6, "zarathustra-birth", "زادروز زرتشت پیامبر", "ancient", "گرامیداشت زادروز زرتشت، پیامبر ایران باستان."),
    (1, 10, "republic-referendum", "همه‌پرسی برای نظام جمهوری اسلامی ایران", "historical", "سالروز همه‌پرسی فروردین ۱۳۵۸."),
    (1, 20, "nuclear-tech-day", "روز ملی فناوری هسته‌ای", "national", ""),
    (1, 25, "attar-day", "بزرگداشت عطار نیشابوری", "cultural", "گرامیداشت عطار نیشابوری، شاعر و عارف ایرانی."),
    (1, 29, "army-day", "روز ارتش جمهوری اسلامی و نیروی زمینی", "national", ""),
    (2, 1, "saadi-day", "بزرگداشت سعدی", "cultural", "گرامیداشت سعدی شیرازی، شاعر و نویسنده بزرگ ایرانی."),
    (2, 10, "persian-gulf-day", "روز ملی خلیج فارس", "national", "گرامیداشت نام و جایگاه خلیج فارس."),
    (2, 12, "teacher-day", "روز معلم", "national", "گرامیداشت مقام معلم و یاد استاد مرتضی مطهری."),
    (2, 25, "ferdowsi-day", "بزرگداشت فردوسی", "cultural", "گرامیداشت حکیم ابوالقاسم فردوسی، سراینده شاهنامه."),
    (2, 25, "persian-language-day", "روز پاسداشت زبان فارسی", "cultural", ""),
    (2, 28, "khayyam-day", "بزرگداشت عمر خیام", "cultural", "گرامیداشت عمر خیام، شاعر و دانشمند ایرانی."),
    (3, 3, "khorramshahr-liberation", "فتح خرمشهر و مقاومت، ایثار و پیروزی", "historical", "سالروز فتح خرمشهر در سال ۱۳۶۱."),
    (3, 6, "khordadgan", "خردادگان", "ancient", "جشن باستانی خردادگان."),
    (4, 7, "judiciary-day", "روز قوه‌ی قضاییه", "national", ""),
    (4, 10, "industry-day", "روز صنعت و معدن", "national", ""),
    (4, 13, "tirgan", "تیرگان", "ancient", "جشن باستانی تیرگان."),
    (4, 14, "pen-day", "روز قلم", "cultural", ""),
    (4, 22, "kharazmi-day", "بزرگداشت خوارزمی", "cultural", "گرامیداشت محمد بن موسی خوارزمی، ریاضی‌دان و اخترشناس ایرانی."),
    (5, 8, "suhrawardi-day", "بزرگداشت سهروردی", "cultural", "گرامیداشت شهاب‌الدین سهروردی، فیلسوف ایرانی."),
    (5, 14, "constitutional-decree", "صدور فرمان مشروطیت", "historical", "سالروز صدور فرمان مشروطیت در ۱۴ مرداد ۱۲۸۵."),
    (5, 17, "journalist-day", "روز خبرنگار", "national", ""),
    (5, 28, "1953-coup", "کودتای ۲۸ مرداد", "historical", "سالروز کودتای ۲۸ مرداد ۱۳۳۲."),
    (6, 1, "avicenna-day", "بزرگداشت ابوعلی سینا", "cultural", "گرامیداشت ابوعلی سینا، پزشک و فیلسوف ایرانی."),
    (6, 1, "physician-day", "روز پزشک", "national", "همزمان با بزرگداشت ابوعلی سینا."),
    (6, 5, "razi-day", "بزرگداشت محمد بن زکریای رازی", "cultural", "گرامیداشت رازی، پزشک و شیمی‌دان ایرانی."),
    (6, 5, "pharmacy-day", "روز داروسازی", "national", ""),
    (6, 11, "printing-day", "روز ملی صنعت چاپ", "national", ""),
    (6, 13, "biruni-day", "بزرگداشت ابوریحان بیرونی", "cultural", "گرامیداشت ابوریحان بیرونی، دانشمند ایرانی."),
    (6, 21, "cinema-day", "روز سینما", "cultural", ""),
    (6, 27, "poetry-day", "روز شعر و ادب فارسی", "cultural", "گرامیداشت روز شعر و ادب فارسی و یاد شهریار."),
    (7, 5, "abadan-siege", "شکست حصر آبادان در عملیات ثامن‌الأئمه", "historical", ""),
    (7, 7, "shams-day", "بزرگداشت شمس", "cultural", "گرامیداشت شمس تبریزی."),
    (7, 8, "rumi-day", "بزرگداشت مولوی", "cultural", "گرامیداشت جلال‌الدین محمد بلخی، شاعر و عارف ایرانی."),
    (7, 10, "mehregan", "مهرگان", "ancient", "جشن باستانی مهرگان."),
    (7, 20, "hafez-day", "بزرگداشت حافظ", "cultural", "گرامیداشت حافظ شیرازی، غزل‌سرای بزرگ ایرانی."),
    (7, 26, "sports-day", "روز تربیت بدنی و ورزش", "national", ""),
    (8, 7, "cyrus-day", "روز کوروش بزرگ", "historical", "گرامیداشت کوروش بزرگ، بنیان‌گذار شاهنشاهی هخامنشی."),
    (8, 24, "book-day", "روز کتاب، کتابخوانی و کتابدار", "cultural", ""),
    (8, 30, "farabi-day", "بزرگداشت ابونصر فارابی", "cultural", "گرامیداشت فارابی، فیلسوف ایرانی."),
    (9, 7, "navy-day", "روز نیروی دریایی", "national", ""),
    (9, 10, "parliament-day", "روز مجلس", "national", ""),
    (9, 12, "constitution-day", "روز قانون اساسی جمهوری اسلامی ایران", "national", ""),
    (9, 16, "student-day", "روز دانشجو", "national", ""),
    (9, 25, "research-day", "روز پژوهش", "national", ""),
    (9, 27, "unity-day", "روز وحدت حوزه و دانشگاه", "national", ""),
    (9, 30, "yalda", "شب یلدا", "ancient", "بلندترین شب سال و یکی از آیین‌های کهن ایرانی."),
    (10, 4, "rudaki-day", "روز بزرگداشت رودکی", "cultural", "گرامیداشت رودکی، پدر شعر فارسی."),
    (10, 20, "amir-kabir-death", "قتل امیرکبیر", "historical", "سالروز قتل میرزا تقی‌خان امیرکبیر."),
    (11, 1, "ferdowsi-birthday", "زادروز فردوسی", "cultural", ""),
    (11, 10, "sadeh", "جشن سده", "ancient", "جشن باستانی سده."),
    (11, 12, "khomeini-return", "بازگشت امام خمینی به ایران", "historical", "سالروز بازگشت امام خمینی در ۱۲ بهمن ۱۳۵۷."),
    (11, 29, "sepandarmazgan", "سپندارمذگان و روز عشق ایرانی", "ancient", "جشن باستانی سپندارمذگان."),
    (12, 5, "khajeh-nasir-day", "بزرگداشت خواجه نصیرالدین طوسی", "cultural", "گرامیداشت خواجه نصیرالدین طوسی، دانشمند و فیلسوف ایرانی."),
    (12, 14, "charity-day", "روز احسان و نیکوکاری", "national", ""),
    (12, 15, "tree-planting-day", "روز درختکاری", "national", ""),
    (12, 21, "nezami-day", "بزرگداشت نظامی گنجوی", "cultural", "گرامیداشت نظامی گنجوی، شاعر ایرانی."),
    (12, 25, "parvin-day", "بزرگداشت پروین اعتصامی", "cultural", "گرامیداشت پروین اعتصامی، شاعر ایرانی."),
]


def main() -> None:
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    holidays = []
    seen = set()
    for year_str, entries in raw.items():
        year = int(year_str)
        for entry in entries:
            hid = entry["id"]
            title, category, description = HOLIDAY_META.get(
                hid, (entry["names"]["fa"], "religious", "")
            )
            month, day = int(entry["month"]), int(entry["day"])
            key = (year, month, day, hid, title)
            if key in seen:
                continue
            seen.add(key)
            holidays.append(
                {
                    "date": f"{year:04d}-{month:02d}-{day:02d}",
                    "id": hid,
                    "title": title,
                    "category": category,
                    "description": description,
                    "source": "jalali-js-holidays",
                }
            )
    holidays.sort(key=lambda e: (e["date"], e["title"]))

    occasions = [
        {
            "month": m,
            "day": d,
            "id": oid,
            "title": title,
            "category": category,
            "description": description,
            "source": "persian-holidays",
        }
        for m, d, oid, title, category, description in OCCASIONS
    ]
    occasions.sort(key=lambda e: (e["month"], e["day"], e["title"]))

    payload = {
        "schema_version": 1,
        "generated_at": "2026-10-27",
        "coverage": {"min_year": 1402, "max_year": 1426},
        "sources": [
            {
                "name": "jalali-js holidays",
                "version": "0.4.2",
                "license": "MIT",
                "url": "https://github.com/yanovian/jalali-js/tree/master/packages/holidays",
                "note": (
                    "Official Iranian holidays for Jalali years 1402-1426; lunar tables "
                    "derived from the University of Tehran Calendar Centre / official "
                    "Iran holiday list."
                ),
            },
            {
                "name": "persian-holidays",
                "version": "1.6.1",
                "license": "MIT",
                "url": "https://github.com/karfekr/persian-holidays",
                "note": "Source of the curated fixed solar occasions in this file.",
            },
        ],
        "holidays": holidays,
        "occasions": occasions,
    }
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    years = sorted({int(h["date"][:4]) for h in holidays})
    print(f"holidays: {len(holidays)} entries, years {years[0]}-{years[-1]}")
    print(f"occasions: {len(occasions)} entries")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
