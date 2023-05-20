# Generated by ChatGPT4

# Python3で、日付と時刻が入力されたら、現在から考えて、次にその日付と時刻を満たすUNIX時間を出力するコードを教えてください

# 例えば、現在は、2023年5月18日です。19日の12時という意味のデータを受け取れば、2023年5月19日の12時という意味の1684465200という出力がほしいです。
# また、3日の15時という意味のデータを受け取れば、2023年6月3日の15時という意味の1685761200という出力がほしいです。

# データのフォーマットは、以下のとおりです

# 日付 時間

# # 5月19日の12時
# 19 12

# # 6月3日の15時
# 3 15
# ----------

# しゅごいでしゅ
# ----------

# 2月に30と入力されても対応できるようにしてください
# ----------

# 日と時間に加え、分も加えたいです。お願いします。
# ----------

import datetime
import time
import calendar


def next_unix_time(day: int, hour: int, minute: int) -> int:
    now = datetime.datetime.now()

    # Check if the day is valid for this month. If not, move to the next month.
    if day > calendar.monthrange(now.year, now.month)[1]:
        if now.month == 12:
            next_datetime = datetime.datetime(now.year + 1, 1, day, hour, minute)
        else:
            next_datetime = datetime.datetime(
                now.year, now.month + 1, day, hour, minute
            )
    elif day < now.day or (
        day == now.day
        and (hour < now.hour or (hour == now.hour and minute <= now.minute))
    ):
        if now.month == 12:
            next_datetime = datetime.datetime(now.year + 1, 1, day, hour, minute)
        else:
            next_datetime = datetime.datetime(
                now.year, now.month + 1, day, hour, minute
            )
    else:
        next_datetime = datetime.datetime(now.year, now.month, day, hour, minute)

    unix_time = int(time.mktime(next_datetime.timetuple()))
    return unix_time


# usage
# day = 19
# hour = 12
# minute = 30
# print(next_unix_time(day, hour, minute))
# print(datetime.datetime.fromtimestamp(next_unix_time(day, hour, minute)))


def get_next_reserve_date(day: int) -> int:
    return next_unix_time(day, 12, 0)
