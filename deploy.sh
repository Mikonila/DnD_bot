#!/bin/bash

# Переменные
SERVER="root@77.73.232.142"
PROJECT_DIR="/root/DND_bot"
LOCAL_DIR="$(pwd)"

# Копируем проект на сервер
rsync -av --exclude '__pycache__' --exclude 'dnd_bot.db' --exclude 'venv' $LOCAL_DIR/ $SERVER:$PROJECT_DIR

# Собираем и запускаем контейнер через ssh
ssh $SERVER << EOF
  cd $PROJECT_DIR
  docker-compose down || true
  docker-compose build
  docker-compose up -d
EOF

echo "Деплой завершён!"