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
from modules import meshidatsu
from modules.base import sql
from modules import mydate

token = "<YOUR SLACK API TOKEN>"
secret = "<YOUR SLACK API SECRET>"

limit = datetime.datetime(1, 1, 1)
last = LST_EMPTY

app = Flask(__name__)
client = WebClient(token=token)
signature_verifier = SignatureVerifier(secret)

pending_data = {}


app = Flask(__name__)
client = WebClient(token=token)
client = WebClient(token=token)
signature_verifier = SignatureVerifier(secret)


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
    def __init__(self, token, channel):
        self.client = WebClient(token=token)
        self.channel = channel

    def post_error_message(self, e):
        error_message = f"例外発生：{str(e)} トレースバック：{traceback.format_exc()}"
        try:
            self.client.chat_postMessage(channel=self.channel, text=error_message)
        except SlackApiError as e:
            print(f"chat_postMessage で例外発生：{str(e)}")

    def handle_message(self, event):
        text = event.get("text", "")
        slack_id = event["user"]
        channel_id = event["channel"]
        # 正規表現パターンにマッチしたとき、関数ポインタを起動する
        for func, regex in func_regex:
            if regex.match(text):
                func(event, slack_id, channel_id)


# r 1 12, .. の日付と時刻の入力が妥当か調べ、タプルの配列を返す
# [(日, 時, 分, isplace2), ...]
def parse_reserve_message(text, channel_id):
    commands = re.sub(r" +", r" ", text)
    commands = re.sub(r", +", r",", commands)
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
            client.chat_postMessage(channel=channel_id, text=f"エラー：{i+1} 番目")
            break
        if length == 3:
            # <PALCE1>|<PALCE2>
            if not re.match(r"^[cfCF]$", elems[0]):
                client.chat_postMessage(
                    channel=channel_id,
                    text=f'<PALCE1>|<PALCE2> エラー：{i+1} 番目、"{elems[0]}"、<PALCE1> か <PALCE2> を選択するために、c か f が使用できます。',
                )
                break
            if place2 and re.match(r"^[cC]$", elems[0]):
                place2 = False
            elif not place2 and re.match(r"^[fF]$", elems[0]):
                place2 = True
        # 2 or 3 のとき
        # 日
        if not re.match(r"^[1-9]|[1-2][0-9]|3[0-1]$", elems[0 + pad]):
            client.chat_postMessage(
                channel=channel_id,
                text=f'日エラー：{i+1} 番目、"{elems[0 + pad]}", カレンダーに存在する日付が使用できます。',
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
            client.chat_postMessage(
                channel=channel_id,
                text=f'時刻エラー：{i+1} 番目、"{elems[1 + pad]}"、時刻は、12:30 から 13:15 まで、15 分刻みで選択できます。',
            )
            break

        result.append((int(elems[0 + pad]), hour, minute, place2))

    return (len(result) != len(commands)), result


def send_que_date(channel_id, unix_times):
    result = [
        f"{mydate.unix_to_reserve_limit(date[0])} {'<PALCE2>' if date[1] else '<PALCE1>'}"
        for date in unix_times
    ]
    result.sort()
    client.chat_postMessage(channel=channel_id, text="\n".join(result))


def handle_request_yes(event, slack_id, channel_id):
    if pending_data.get(slack_id) is None:
        client.chat_postMessage(
            channel=channel_id, text="承認エラー：あなたのリクエストは一時キューに登録されていません。"
        )
        return
    with sql.MeshiReserveDB() as db:
        db.insert_temp_to_que(slack_id, pending_data[slack_id])
    del pending_data[slack_id]
    client.chat_postMessage(
        channel=channel_id, text="あなたのリクエストがキューへ登録されました。reserve で今すぐ予約を実行できます。"
    )


def handle_request_no(event, slack_id, channel_id):
    if pending_data.get(slack_id) is None:
        client.chat_postMessage(
            channel=channel_id, text="承認エラー：あなたのリクエストは一時キューに登録されていません。"
        )
        return
    del pending_data[slack_id]
    client.chat_postMessage(channel=channel_id, text="あなたのリクエストが一時キューから削除されました。")


def handle_request_showt(event, slack_id, channel_id):
    if pending_data.get(slack_id) is None:
        client.chat_postMessage(
            channel=channel_id,
            text="一時キューは空です。r コマンドで一時キューに登録してください。",
        )
        return
    client.chat_postMessage(
        channel=channel_id,
        text="一時キューに入っているリスト：",
    )
    send_que_date(channel_id, pending_data[slack_id])


def handle_request_reserve(event, slack_id, channel_id):
    global limit, last
    with sql.MeshiReserveDB() as db:
        ques = db.select_all_que_where_slack_id(slack_id)
    if not ques:
        client.chat_postMessage(
            channel=channel_id,
            text="予約キューは空です。r コマンドと yes コマンドで予約キューに登録してください",
        )
        return
    send_que_date(channel_id, ques)
    client.chat_postMessage(
        channel=channel_id,
        text=f"本当に今すぐ予約しますか？予約する場合は、1 分以内に execute を実行してください。",
    )
    limit = datetime.datetime.now()
    last = LST_RESERVE


# 予約キューの実行を行い、結果を表示する
def handle_request_execute(event, slack_id, channel_id):
    global limit, last
    client.chat_postMessage(
        channel=channel_id,
        text=f"予約を開始します。",
    )
    if last != LST_RESERVE or limit == LST_EMPTY:
        client.chat_postMessage(
            channel=channel_id,
            text=f"まず reserve で予約内容が正しいかどうかを確認してください。",
        )
        return
    if datetime.datetime.now() - limit > datetime.timedelta(seconds=60):
        client.chat_postMessage(
            channel=channel_id,
            text=f"reserve で確認してから 1 分以上経ちました。もう一度確認してから実行してください。",
        )
        return

    with meshidatsu.WebDriverWithDB() as handler:
        result = handler.reserve_from_slack_id(slack_id)
        account_result = handler.retr_reserved_data_from_account()
        full_result = handler.retr_reserved_with_rand_from_account(account_result)
        answer = []
        for_insert = []
        for e in full_result:
            for r in result:
                if e[RSV_START] == r[QUE_START]:
                    if e[RSV_PLACE] == "<PALCE2>" and r[QUE_PLACE] == 1:
                        answer.append(
                            f"{e[RSV_DATE]} {mydate.gen_day(e[RSV_START])} {e[RSV_TIME]} {e[RSV_PLACE]} {e[RSV_IDWR]} {r[2]}"
                        )
                    elif e[RSV_PLACE] == "<PALCE1>" and r[QUE_PLACE] == 0:
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
                f"{'<PALCE2>' if r[QUE_PLACE] else '<PALCE1>'} {r[2]}"
            )

        answer = "\n".join(answer)
        client.chat_postMessage(
            channel=channel_id,
            text=f"{answer}\n予約が完了しました。",
        )

    limit = LST_EMPTY
    last = LST_EMPTY


def handle_request_showq(event, slack_id, channel_id):
    with sql.MeshiReserveDB() as db:
        ques = db.select_all_que_where_slack_id(slack_id)
    if not ques:
        client.chat_postMessage(
            channel=channel_id,
            text="予約キューは空です。r コマンドと yes コマンドで予約キューに登録してください。",
        )
        return
    client.chat_postMessage(
        channel=channel_id,
        text="予約キューに入っているリスト：",
    )
    send_que_date(channel_id, ques)


def handle_request_insert_temp(event, slack_id, channel_id):
    if pending_data.get(slack_id) is not None:
        client.chat_postMessage(
            channel=channel_id,
            text=f"登録エラー：既に一時キューへあなたのリクエストが登録されています。リクエストを確認して、予約キューへ入れるか、削除してからもう一度試してください。",
        )
        return
    error, reqs = parse_reserve_message(event["text"], channel_id)
    if error:
        return
    unix_times = [[mydate.next_unix_time(r[0], r[1], r[2]), r[3]] for r in reqs]
    pending_data[slack_id] = unix_times
    send_que_date(channel_id, unix_times)
    client.chat_postMessage(
        channel=channel_id,
        text="あなたのリクエストを一時キューへ登録しました。上記表示が正しければ、yes と送ることで、予約キューへ入れることが来ます。no でキャンセルできます。",
    )


# [["2023/05/23 火 13:00 - 13:30 <PLACE2> R0345833_768c", <QR code PATH>], ...]
def handle_request_qr(event, slack_id, channel_id):
    today = mydate.gen_today()
    # today = mydate.gen_next_date(23)
    with sql.MeshiReserveDB() as db:
        result = db.select_all_reserved_date_where_date(today)
    if not result:
        client.chat_postMessage(
            channel=channel_id,
            text="今日の予約は存在しません。",
        )
        return None
    client.chat_postMessage(
        channel=channel_id,
        text="QR コードを生成します。",
    )
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
        client.chat_postMessage(channel=channel_id, text=qr[0])
        client.files_upload_v2(channel=channel_id, file=qr[1])


def handle_request_refresh(event, slack_id, channel_id):
    client.chat_postMessage(
        channel=channel_id,
        text="予約済みリストを更新します。",
    )
    with meshidatsu.WebDriverWithDB() as driver:
        driver.insert_current_account_all_reserved()
    client.chat_postMessage(
        channel=channel_id,
        text="更新しました。",
    )


def handle_request_showr(event, slack_id, channel_id):
    with sql.MeshiReserveDB() as db:
        reserveds = db.select_all_reserved_data()
    if not reserveds:
        client.chat_postMessage(
            channel=channel_id,
            # 今後時限式に変更する
            text="予約済みリストは空です。r コマンドと yes コマンドで予約キューに登録し、reserve で予約を実行してください。",
        )
        return
    client.chat_postMessage(
        channel=channel_id,
        text="予約済みに入っているリスト：",
    )
    send_reserved_date(channel_id, reserveds)


def send_reserved_date(channel_id, reserveds):
    result = [
        f"{mydate.unix_to_reserve_limit(tup[RSV_START])} {tup[RSV_PLACE]} {tup[RSV_IDWR]}"
        for tup in reserveds
    ]
    result.sort()
    client.chat_postMessage(channel=channel_id, text="\n".join(result))


def handle_request_cancel(event, slack_id, channel_id):
    client.chat_postMessage(
        channel=channel_id,
        text="予約済みリストを取得します。",
    )
    with sql.MeshiReserveDB() as db:
        reserveds = db.select_all_reserved_data()
    if not reserveds:
        client.chat_postMessage(
            channel=channel_id,
            text="予約済みリストは空です。refresh コマンドで現在の予約状況を取得できます。",
        )
        return

    # この関数が呼び出されるまでに例外は省かれているはず
    request = "_" + re.search(r"[a-f0-9]{4}", event["text"])[0]
    for reserve in reserveds:
        if request in reserve[RSV_IDWR]:
            client.chat_postMessage(
                channel=channel_id,
                text="一致する予約を発見しました。",
            )
            if reserve[RSV_START] + RESERVE_LIMIT < int(time.time()):
                client.chat_postMessage(
                    channel=channel_id,
                    text="予約時刻を過ぎているため、キャンセルできません。リストから削除します。",
                )
                with sql.MeshiReserveDB() as db:
                    db.delete_reserved_where_reserved_id_with_rand(reserve[RSV_IDWR])
                client.chat_postMessage(
                    channel=channel_id,
                    text="削除しました。",
                )
                return
            send_reserved_date(channel_id, [reserve])
            client.chat_postMessage(
                channel=channel_id,
                text="キャンセルを実行します。",
            )
            with meshidatsu.WebDriverWithDB() as handler:
                handler.cancel(reserve[RSV_ID])
                new_reserveds = handler.retr_reserved_data_from_account()
                for res in new_reserveds:
                    if res[RSV_ID] == reserve[RSV_ID]:
                        client.chat_postMessage(
                            channel=channel_id,
                            text="キャンセルに失敗しました。再度実行してみてください。",
                        )
                        return
                client.chat_postMessage(
                    channel=channel_id,
                    text="キャンセルに成功しました。予約済みリストから削除します。",
                )
                handler.delete_reserved_where_reserved_id_with_rand(reserve[RSV_IDWR])
            return

    client.chat_postMessage(
        channel=channel_id,
        text="一致する予約が見つかりませんでした。showr で現在の予約済みリストを確認できます。",
    )


# アカウントが 1 つであることが前提となっている
def handle_request_validate(event, slack_id, channel_id):
    client.chat_postMessage(
        channel=channel_id,
        text="予約済みリストを検証します。",
    )
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
            client.chat_postMessage(
                channel=channel_id,
                text="予約済みリストは、全て有効であることを確認しました。",
            )
            return

        client.chat_postMessage(
            channel=channel_id,
            text="予約済みリストに無効な予約が含まれていました。",
        )
        send_reserved_date(channel_id, not_found)
        client.chat_postMessage(
            channel=channel_id,
            text="削除を実行します。",
        )
        print(not_found_idwithrand)
        for idwr in not_found_idwithrand:
            handler.delete_reserved_where_reserved_id_with_rand(idwr)
        client.chat_postMessage(
            channel=channel_id,
            text="削除が完了しました。",
        )


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
        slack_bot = SlackBot(token, event["channel"])
        try:
            slack_bot.handle_message(event)
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
    ]

    # 上記正規表現パターンを事前コンパイル
    func_regex = [(func, re.compile(regex)) for func, regex in func_regex]

    # 1 つのメッセージに対する多重レスポンスを避けるための event_id キャッシュ
    received_events = LRUCache(100)

    app.run(port=3000, debug=True, host="0.0.0.0")
