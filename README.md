# scheduler
디스코드 일정 알림 봇

## schedules 저장 방식
```json
[
    {
        "server": 서버 ID (Integer),
        "channel": 채널 ID (Integer),
        "message": 알림 메시지 (String),
        "user": 사용자 ID (Integer),
        "date": 시작 일시 Epoch (Integer),
        "interval": 알림 간격 Epoch (Integer),
        "last": 마지막 알림 일시 Epoch (Integer)
    }
]
```