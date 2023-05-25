import re
import time
import datetime
import traceback
from slack_sdk import WebClient
from slack_sdk.web import WebClient
from flask import Flask, request, jsonify
from slack_sdk.errors import SlackApiError
from slack_sdk.signature import SignatureVerifier
from collections import OrderedDict

from modules.base.myconst import *
from modules.base import myfirefox
from modules import meshidatsu
from modules.base import sql
from modules import mydate

limit = datetime.datetime(1, 1, 1)
last = LST_EMPTY

pending_data = {}


app = Flask(__name__)
signature_verifier = SignatureVerifier(SECRET)


class LRUCache:
    def __init__(self, maxsize):
        self.cache = OrderedDict()
        self.maxsize = maxsize

    def add(self, key, value):
        self.cache[key] = value
        if len(self.cache) > self.maxsize:
            self.cache.popitem(last=False)

    def get(self, key):
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        return None

    def __contains__(self, key):
        return key in self.cache


class SlackBot:
    def __init__(self, token, event):
        self.client = WebClient(token=token)
        self.event = event
        self.text = self.event.get("text", "")
        self.slack_id = self.event["user"]
        self.channel_id = self.event["channel"]

    def text(self):
        return self.text

    def user_id(self):
        return self.slack_id

    def channel_id(self):
        return self.channel_id

    def post_message(self, text):
        response = self.client.chat_postMessage(channel=self.channel_id, text=text)
        return response

    def upload_file(self, file_path):
        response = self.client.files_upload_v2(channels=self.channel_id, file=file_path)
        return response

    def post_error_message(self, e):
        error_message = f"例外発生：{str(e)} トレースバック：{traceback.format_exc()}"
        try:
            self.post_message(text=error_message)
        except SlackApiError as e:
            print(f"post_message で例外発生：{str(e)}")

    def handle_message(self):
        # 正規表現パターンにマッチしたとき、関数ポインタを起動する
        for func, regex in func_regex:
            if regex.match(self.text):
                func(self)


# r 1 12, .. の日付と時刻の入力が妥当か調べ、タプルの配列を返す
# [(日, 時, 分, isplace2), ...]
def parse_reserve_message(slack_bot: SlackBot):
    commands = re.sub(r" +", r" ", slack_bot.text())
    commands = re.sub(r" *, +", r",", commands)
    commands = re.sub(r"^(R|r) +", r"", commands)
    commands = commands.strip().split(",")

    place2 = True
    result = []
    for i, command in enumerate(commands):
        elems = command.split(" ")
        length = len(elems)
        # 添字の調整 True のとき int の 1 に変換される
        pad = len(elems) == 3
        if length != 2 and length != 3:
            slack_bot.post_message(f"エラー：{i+1} 番目")
            break
        if length == 3:
            # <PLACE1>|<PLACE2>
            if not re.match(r"^[cfCF]$", elems[0]):
                slack_bot.post_message(
                    f'<PLACE1>|<PLACE2> エラー：{i+1} 番目、"{elems[0]}"、<PLACE1> か <PLACE2> を選択するために、c か f が使用できます。'
                )
                break
            if place2 and re.match(r"^[cC]$", elems[0]):
                place2 = False
            elif not place2 and re.match(r"^[fF]$", elems[0]):
                place2 = True
        # 2 or 3 のとき
        # 日
        if not re.match(r"^[1-9]|[1-2][0-9]|3[0-1]$", elems[0 + pad]):
            slack_bot.post_message(
                f'日エラー：{i+1} 番目、"{elems[0 + pad]}", カレンダーに存在する日付が使用できます。'
            )
            break
        # 時間
        hour = 0
        minute = 0
        if re.match(r"^1[2-3]$", elems[1 + pad]):
            hour = int(elems[1 + pad])
        elif re.match(r"^12:(0|00|15|30|45)|13:(0|00|15)$", elems[1 + pad]):
            hm = elems[1 + pad].split(":")
            hour = int(hm[0])
            minute = int(hm[1])
        else:
            slack_bot.post_message(
                f'時刻エラー：{i+1} 番目、"{elems[1 + pad]}"、時刻は、12:30 から 13:15 まで、15 分刻みで選択できます。'
            )
            break

        result.append((int(elems[0 + pad]), hour, minute, place2))

    return (len(result) != len(commands)), result


def send_que_date(slack_bot: SlackBot, unix_times):
    result = [
        f"{mydate.unix_to_reserve_limit(date[0])} {'<PLACE2>' if date[1] else '<PLACE1>'}"
        for date in unix_times
    ]
    result.sort()
    slack_bot.post_message("\n".join(result))


def handle_request_yes(slack_bot: SlackBot):
    if pending_data.get(slack_bot.user_id()) is None:
        slack_bot.post_message("承認エラー：あなたのリクエストは一時キューに登録されていません。")
        return
    with sql.MeshiReserveDB() as db:
        db.insert_temp_to_que(slack_bot.user_id(), pending_data[slack_bot.user_id()])
    del pending_data[slack_bot.user_id()]
    slack_bot.post_message("あなたのリクエストがキューへ登録されました。reserve で今すぐ予約を実行できます。")


def handle_request_no(slack_bot: SlackBot):
    if pending_data.get(slack_bot.slack_id()) is None:
        slack_bot.post_message("承認エラー：あなたのリクエストは一時キューに登録されていません。")
        return
    del pending_data[slack_bot.slack_id()]
    slack_bot.post_message("あなたのリクエストが一時キューから削除されました。")


def handle_request_showt(slack_bot: SlackBot):
    if pending_data.get(slack_bot.user_id()) is None:
        slack_bot.post_message("一時キューは空です。r コマンドで一時キューに登録してください。")
        return
    slack_bot.post_message("一時キューに入っているリスト：")
    send_que_date(slack_bot, pending_data[slack_bot.user_id()])


def handle_request_reserve(slack_bot: SlackBot):
    global limit, last
    with sql.MeshiReserveDB() as db:
        ques = db.select_all_que_where_slack_id(slack_bot.user_id())
    if not ques:
        slack_bot.post_message("予約キューは空です。r コマンドと yes コマンドで予約キューに登録してください")
        return
    send_que_date(slack_bot, ques)
    slack_bot.post_message("本当に今すぐ予約しますか？予約する場合は、1 分以内に execute を実行してください。")
    limit = datetime.datetime.now()
    last = LST_RESERVE


# 予約キューの実行を行い、結果を表示する
def handle_request_execute(slack_bot: SlackBot):
    global limit, last
    slack_bot.post_message("予約を開始します。")
    if last != LST_RESERVE or limit == LST_EMPTY:
        slack_bot.post_message("まず reserve で予約内容が正しいかどうかを確認してください。")
        return
    if datetime.datetime.now() - limit > datetime.timedelta(seconds=60):
        slack_bot.post_message("reserve で確認してから 1 分以上経ちました。もう一度確認してから実行してください。")
        return

    with meshidatsu.WebDriverWithDB() as handler:
        result = handler.reserve_from_slack_id(slack_bot.user_id())
        account_result = handler.retr_reserved_data_from_account()
        full_result = handler.retr_reserved_with_rand_from_account(account_result)
        answer = []
        for_insert = []
        for e in full_result:
            for r in result:
                if e[RSV_START] == r[QUE_START]:
                    if e[RSV_PLACE] == "<PLACE2>" and r[QUE_PLACE] == 1:
                        answer.append(
                            f"{e[RSV_DATE]} {mydate.gen_day(e[RSV_START])} {e[RSV_TIME]} {e[RSV_PLACE]} {e[RSV_IDWR]} {r[2]}"
                        )
                    elif e[RSV_PLACE] == "<PLACE1>" and r[QUE_PLACE] == 0:
                        answer.append(
                            f"{e[RSV_DATE]} {mydate.gen_day(e[RSV_START])} {e[RSV_TIME]} {e[RSV_PLACE]} {e[RSV_IDWR]} {r[2]}"
                        )
                    for_insert.append(e)
        handler.insert_reserved_data(for_insert)
        for r in result:
            if r[2] == "予約成功":
                continue
            answer.append(
                f"{mydate.unix_to_reserve_limit(r[QUE_START])} "
                f"{'<PLACE2>' if r[QUE_PLACE] else '<PLACE1>'} {r[2]}"
            )

        answer = "\n".join(answer)
        slack_bot.post_message(f"{answer}\n予約が完了しました。")

    limit = LST_EMPTY
    last = LST_EMPTY


def handle_request_showq(slack_bot: SlackBot):
    with sql.MeshiReserveDB() as db:
        ques = db.select_all_que_where_slack_id(slack_bot.user_id())
    if not ques:
        slack_bot.post_message("予約キューは空です。r コマンドと yes コマンドで予約キューに登録してください。")
        return
    slack_bot.post_message("予約キューに入っているリスト：")
    send_que_date(slack_bot, ques)


def handle_request_insert_temp(slack_bot: SlackBot):
    if pending_data.get(slack_bot.user_id()) is not None:
        slack_bot.post_message(
            "登録エラー：既に一時キューへあなたのリクエストが登録されています。リクエストを確認して、予約キューへ入れるか、削除してからもう一度試してください。"
        )
        return
    error, reqs = parse_reserve_message(slack_bot.text(), slack_bot.channel_id())
    if error:
        return
    unix_times = [[mydate.next_unix_time(r[0], r[1], r[2]), r[3]] for r in reqs]
    pending_data[slack_bot.user_id()] = unix_times
    send_que_date(slack_bot, unix_times)
    slack_bot.post_message(
        "あなたのリクエストを一時キューへ登録しました。上記表示が正しければ、yes と送ることで、予約キューへ入れることが来ます。no でキャンセルできます。"
    )


# [["2023/05/23 火 13:00 - 13:30 <PLACE2> R0345833_768c", <QR code PATH>], ...]
def handle_request_qr(slack_bot: SlackBot):
    today = mydate.gen_today()
    # today = mydate.gen_next_date(23)
    with sql.MeshiReserveDB() as db:
        result = db.select_all_reserved_date_where_date(today)
    if not result:
        slack_bot.post_message("今日の予約は存在しません。")
        return None
    slack_bot.post_message("QR コードを生成します。")
    res = []
    with meshidatsu.WebDriverWithDB() as driver:
        for e in result:
            res.append(
                [
                    f"{e[RSV_DATE]} {mydate.gen_day(e[RSV_START])} {e[RSV_TIME]} {e[RSV_PLACE]} {e[RSV_IDWR]}",
                    driver.generate_qr(e[RSV_IDWR]),
                ]
            )

    for qr in res:
        slack_bot.post_message(qr[0])
        slack_bot.upload_file(qr[1])


def handle_request_refresh(slack_bot: SlackBot):
    slack_bot.post_message("予約済みリストを更新します。")
    with meshidatsu.WebDriverWithDB() as driver:
        driver.insert_current_account_all_reserved()
    slack_bot.post_message("更新しました。")


def handle_request_showr(slack_bot: SlackBot):
    with sql.MeshiReserveDB() as db:
        reserveds = db.select_all_reserved_data()
    if not reserveds:
        # 今後時限式に変更する
        slack_bot.post_message(
            "予約済みリストは空です。r コマンドと yes コマンドで予約キューに登録し、reserve で予約を実行してください。"
        )
        return
    slack_bot.post_message("予約済みに入っているリスト：")
    send_reserved_date(slack_bot, reserveds)


def send_reserved_date(slack_bot: SlackBot, reserveds):
    result = [
        f"{mydate.unix_to_reserve_limit(tup[RSV_START])} {tup[RSV_PLACE]} {tup[RSV_IDWR]}"
        for tup in reserveds
    ]
    result.sort()
    slack_bot.post_message("\n".join(result))


def handle_request_cancel(slack_bot: SlackBot):
    slack_bot.post_message("予約済みリストを取得します。")
    with sql.MeshiReserveDB() as db:
        reserveds = db.select_all_reserved_data()
    if not reserveds:
        slack_bot.post_message("予約済みリストは空です。refresh コマンドで現在の予約状況を取得できます。")
        return

    # この関数が呼び出されるまでに例外は省かれているはず
    request = "_" + re.search(r"[a-f0-9]{4}", slack_bot.text())[0]
    for reserve in reserveds:
        if request in reserve[RSV_IDWR]:
            slack_bot.post_message("一致する予約を発見しました。")
            if reserve[RSV_START] + RESERVE_LIMIT < int(time.time()):
                slack_bot.post_message("予約時刻を過ぎているため、キャンセルできません。リストから削除します。")
                with sql.MeshiReserveDB() as db:
                    db.delete_reserved_where_reserved_id_with_rand(reserve[RSV_IDWR])
                slack_bot.post_message("削除しました。")
                return
            send_reserved_date(slack_bot, [reserve])
            slack_bot.post_message("キャンセルを実行します。")
            with meshidatsu.WebDriverWithDB() as handler:
                handler.cancel(reserve[RSV_ID])
                new_reserveds = handler.retr_reserved_data_from_account()
                for res in new_reserveds:
                    if res[RSV_ID] == reserve[RSV_ID]:
                        slack_bot.post_message("キャンセルに失敗しました。再度実行してみてください。")
                        return
                slack_bot.post_message("キャンセルに成功しました。予約済みリストから削除します。")
                handler.delete_reserved_where_reserved_id_with_rand(reserve[RSV_IDWR])
            return

    slack_bot.post_message("一致する予約が見つかりませんでした。showr で現在の予約済みリストを確認できます。")


# アカウントが 1 つであることが前提となっている
def handle_request_validate(slack_bot: SlackBot):
    slack_bot.post_message("予約済みリストを検証します。")
    with meshidatsu.WebDriverWithDB() as handler:
        cur_reserved = handler.retr_reserved_data_from_account()
        db_reserved = handler.select_all_reserved_data()
        not_found = []
        not_found_idwithrand = []
        for db in db_reserved:
            for cur in cur_reserved:
                if db[RSV_ID] == cur[RSV_ID]:
                    break
            # if に引っかからなかった時に実行
            else:
                not_found.append(db)
                not_found_idwithrand.append(db[RSV_IDWR])

        if not not_found:
            slack_bot.post_message("予約済みリストは、全て有効であることを確認しました。")
            return

        slack_bot.post_message("予約済みリストに無効な予約が含まれていました。")
        send_reserved_date(slack_bot, not_found)
        slack_bot.post_message("削除を実行します。")
        print(not_found_idwithrand)
        for idwr in not_found_idwithrand:
            handler.delete_reserved_where_reserved_id_with_rand(idwr)
        slack_bot.post_message("削除が完了しました。")


def handle_request_status(slack_bot: SlackBot):
    slack_bot.post_message("現在の予約状況を取得します。")
    with myfirefox.MeshiDatsuDriver() as driver:
        driver.count_more()
        result = driver.retr_current_reserve_status()
    slack_bot.post_message(result)


@app.route("/slack/events", methods=["POST"])
def slack_event():
    if not signature_verifier.is_valid_request(request.get_data(), request.headers):
        return "invalid request", 403

    payload = request.json

    # サーバの有効性確認用
    if payload.get("type") == "url_verification":
        return jsonify({"challenge": payload.get("challenge")})

    # レスポンスが遅いことによる単一メッセージからの複数レスポンスを回避
    event_id = payload.get("event_id", None)
    if event_id is None or received_events.get(event_id):
        return "", 200
    received_events.add(event_id, True)

    # BOT のメッセージは無視
    event = payload.get("event", {})
    if "bot_id" in event:
        return "", 200

    # ユーザからのメッセージのとき、処理を行う
    if event.get("type") == "message":
        slack_bot = SlackBot(TOKEN, event)
        try:
            slack_bot.handle_message()
        except Exception as e:
            slack_bot.post_error_message(e)

    return "", 200


if __name__ == "__main__":
    # (関数ポインタ, 正規表現パターン)
    func_regex = [
        (handle_request_insert_temp, r"^(R|r) +[cf0-9 ,:]+$"),
        (handle_request_yes, r"^(Y|y)es *$"),
        (handle_request_no, r"^(N|n)o *$"),
        (handle_request_showt, r"^(S|s)howt *$"),
        (handle_request_reserve, r"^(R|r)eserve *$"),
        (handle_request_showq, r"^(S|s)howq *$"),
        (handle_request_execute, r"^(E|e)xecute *$"),
        (handle_request_qr, r"^(Q|q)r *$"),
        (handle_request_refresh, r"^(R|r)efresh *$"),
        (handle_request_showr, r"^(S|s)howr *$"),
        (handle_request_cancel, r"^(C|c)ancel +[a-f0-9]{4} *$"),
        (handle_request_validate, r"^(V|v)alidate *$"),
        (handle_request_status, r"^(S|s)tatus *$"),
    ]

    # 上記正規表現パターンを事前コンパイル
    func_regex = [(func, re.compile(regex)) for func, regex in func_regex]

    # 1 つのメッセージに対する多重レスポンスを避けるための event_id キャッシュ
    received_events = LRUCache(100)

    app.run(port=3000, debug=True, host="0.0.0.0")
