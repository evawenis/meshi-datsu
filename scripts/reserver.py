# # [[2023/05/23 火 13:00 - 13:30 <PLACE2> R0345833_768c, <QR code PATH>], ...]
# def retr_today_qr(driver):
#     # today = mydate.gen_today()
#     today = mydate.gen_next_date(23)
#     result = sql.select_by_date_from_reserved(today)
#     if not result:
#         print("Yon have not reserved today's meshi.")
#         return None

#     res = []
#     for e in result:
#         res.append(
#             [
#                 f"{e[RSV_DATE]} {mydate.gen_day(e[RSV_START])} {e[RSV_TIME]} {e[RSV_IDWR]}",
#                 genqr.generate_qr(driver, e[RSV_END]),
#             ]
#         )

#     return res


# # def scheduler(driver):
# #     now = datetime.now()
# #     now = datetime(now.year, now.month, now.day, now.hour, now.minute, now.second)
# #     comp = datetime.strptime(SCHEDULE, "%Y-%m-%d %H:%M:%S.%f")
# #     diff = comp - now

# #     if diff.days < 0:
# #         print("error: the scheduled time went over.", file=sys.stderr)
# #         return

# #     print(
# #         f"waiting {diff}, until {datetime.strptime(SCHEDULE, '%Y-%m-%d %H:%M:%S.%f')}",
# #         file=sys.stderr,
# #     )
# #     scheduler = sched.scheduler(time.time, time.sleep)
# #     scheduler.enter(diff.seconds, 1, run, (driver,))
# #     scheduler.run()

# テスト目的

from selenium.webdriver.common.by import By
from modules.base.myconst import *
from modules import meshidatsu
from modules.base.myfirefox import *
from modules.base.sql import *
import code

with MeshiDatsuDriver() as driver:
    with MeshiReserveDB() as db:
        code.InteractiveConsole(globals()).interact()
