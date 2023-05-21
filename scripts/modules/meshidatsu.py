from modules.base import myfirefox
from modules.base.myconst import *
from modules.base import sql


class WebDriverWithDB(myfirefox.MeshiDatsuDriver, sql.MeshiReserveDB):
    def __init__(
        self,
        strategy=STRATEGY,
        wait_time=WAIT_TIME,
        user_id=ID,
        passwd=PW,
        account_url=ACCOUNT_URL,
        reserve_url=RESERVE_URL,
        token_url=TOKEN_URL,
        host="mysql",
        database="MeshiReserve",
        user="root",
        password="root",
    ):
        myfirefox.MeshiDatsuDriver.__init__(
            self=self,
            strategy=strategy,
            wait_time=wait_time,
            user_id=user_id,
            passwd=passwd,
            account_url=account_url,
            reserve_url=reserve_url,
            token_url=token_url,
        )
        sql.MeshiReserveDB.__init__(self, host, database, user, password)

    def __enter__(self):
        myfirefox.MeshiDatsuDriver.__enter__(self)
        sql.MeshiReserveDB.__enter__(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        super().__exit__(exc_type, exc_val, exc_tb)

    # slack id を受け取り、そのユーザの予約キューを実行する
    # 実行結果を返す
    def reserve_from_slack_id(self, slack_id):
        try:
            # 実行する予約データを SQL から取得
            ques = super().select_all_que_where_slack_id(slack_id)
            super().login()

            # 予約処理の実行と結果取得
            result = [
                (
                    q[QUE_START],
                    q[QUE_PLACE],
                    myfirefox.MeshiDatsuDriver.reserve(
                        self, q[QUE_START], q[QUE_PLACE]
                    ),
                    # super().reserve(q[QUE_START], q[QUE_PLACE]),
                )
                for q in ques
            ]
            return result
        finally:
            # エラーが発生してもキューの内容を削除
            super().delete_all_que_where_slack_id(slack_id)

    # アカウントの予約データをすべて reserved に登録する
    def insert_current_account_all_reserved(self):
        # SQL へ入力する用のデータ（乱数付き予約番号以外）を取得
        tmplist = super().retr_reserved_data_from_account()
        # 上で取得したものに、乱数付き予約番号を付加したものを取得
        result = super().retr_reserved_with_rand_from_account(tmplist)
        # SQL に登録
        super().insert_reserved_data(result)
