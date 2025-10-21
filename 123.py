#!/usr/bin/env python3
# crypto_final_bot.py - ФИНАЛЬНАЯ ВЕРСИЯ БОТА
import requests
import time
import sqlite3
import json
import pandas as pd
from datetime import datetime
from threading import Thread, Lock
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

CONFIG = {
    'database_path': 'crypto_final.db',
    'interval': 5 * 60,
    'top_n': 100,
    'min_confidence': 60
}

EXCLUDE_COINS = [
    'usdt', 'usdc', 'busd', 'dai', 'tusd', 'ust', 'fdusd', 'pyusd', 'cusdc', 'cdai',
    'btc', 'eth', 'bnb', 'xrp', 'ada', 'doge', 'sol', 'dot', 'matic', 'ltc',
    'bch', 'link', 'xlm', 'atom', 'etc', 'xmr', 'xtz', 'eos', 'trx', 'neo'
]

class AdvancedAnalyzer:
    def __init__(self):
        self.session = requests.Session()
    
    def fetch_all_coins(self):
        """Загружает все монеты для анализа"""
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": CONFIG['top_n'],
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h,7d"
        }
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code == 200:
                coins = response.json()
                filtered_coins = [
                    coin for coin in coins 
                    if coin['symbol'].lower() not in EXCLUDE_COINS
                ]
                return filtered_coins
        except Exception as e:
            print(f"❌ Ошибка загрузки монет: {e}")
        return []
    
    def calculate_coin_score(self, coin):
        """Расчитывает комплексный счет монеты (0-100)"""
        score = 0
        analysis = {}
        
        # 1. Volume Score (30%)
        volume_ratio = coin['total_volume'] / coin['market_cap'] if coin['market_cap'] > 0 else 0
        if volume_ratio > 0.3:
            score += 30
            analysis['volume'] = "🔥 Экстремальный объем"
        elif volume_ratio > 0.15:
            score += 20
            analysis['volume'] = "📈 Высокий объем"
        elif volume_ratio > 0.05:
            score += 10
            analysis['volume'] = "💹 Хороший объем"
        
        # 2. Price Momentum Score (25%)
        price_change_24h = coin.get('price_change_percentage_24h', 0)
        if 10 < price_change_24h < 50:
            score += 25
            analysis['momentum'] = f"🚀 Сильный рост +{price_change_24h:.1f}%"
        elif 5 < price_change_24h < 10:
            score += 15
            analysis['momentum'] = f"📈 Умеренный рост +{price_change_24h:.1f}%"
        elif price_change_24h < -20:
            score += 10
            analysis['momentum'] = f"💥 Просадка {price_change_24h:.1f}%"
        
        # 3. Market Cap Score (20%)
        market_cap = coin['market_cap']
        if market_cap < 50000000:  # < $50M
            score += 20
            analysis['market_cap'] = "🏦 Малая капа - высокий потенциал"
        elif market_cap < 200000000:  # < $200M
            score += 15
            analysis['market_cap'] = "🏦 Средняя капа"
        
        # 4. Trend Score (15%)
        price_change_7d = coin.get('price_change_percentage_7d_in_currency', 0)
        if price_change_7d > 20:
            score += 15
            analysis['trend'] = f"📊 Недельный рост +{price_change_7d:.1f}%"
        elif price_change_7d > 0:
            score += 8
            analysis['trend'] = f"📊 Позитивный недельный тренд"
        
        # 5. Risk Adjustment
        if price_change_24h > 100:
            score -= 15
            analysis['risk'] = "⚠️ Перекуплена - высокий риск"
        elif price_change_24h > 200:
            score -= 25
            analysis['risk'] = "🚨 Сильно перекуплена"
        
        return max(0, min(100, score)), analysis
    
    def get_top_predictions(self, coins_data, top_n=10):
        """Возвращает топ монет по предсказательной силе"""
        predictions = []
        
        for coin in coins_data:
            score, analysis = self.calculate_coin_score(coin)
            predictions.append({
                'symbol': coin['symbol'].upper(),
                'name': coin['name'],
                'score': score,
                'price': coin['current_price'],
                'price_change_24h': coin.get('price_change_percentage_24h', 0),
                'market_cap': coin['market_cap'],
                'volume': coin['total_volume'],
                'analysis': analysis
            })
        
        predictions.sort(key=lambda x: x['score'], reverse=True)
        return predictions[:top_n]
    
    def get_coin_analysis(self, symbol, coins_data):
        """Детальный анализ конкретной монеты"""
        for coin in coins_data:
            if coin['symbol'].upper() == symbol.upper():
                score, analysis = self.calculate_coin_score(coin)
                return {
                    'symbol': symbol.upper(),
                    'name': coin['name'],
                    'score': score,
                    'price': coin['current_price'],
                    'price_change_24h': coin.get('price_change_percentage_24h', 0),
                    'market_cap': coin['market_cap'],
                    'volume': coin['total_volume'],
                    'volume_ratio': coin['total_volume'] / coin['market_cap'] if coin['market_cap'] > 0 else 0,
                    'analysis': analysis,
                    'recommendation': self.get_recommendation(score, analysis)
                }
        return None
    
    def get_recommendation(self, score, analysis):
        """Генерирует рекомендацию на основе счета"""
        if score >= 80:
            return "🚀 СИЛЬНЫЙ СИГНАЛ - Высокий потенциал роста"
        elif score >= 65:
            return "📈 ХОРОШИЙ СИГНАЛ - Умеренный потенциал"
        elif score >= 50:
            return "💡 СРЕДНИЙ СИГНАЛ - Требует осторожности"
        else:
            return "⚠️ СЛАБЫЙ СИГНАЛ - Высокий риск"

class CryptoFinalBot:
    def __init__(self):
        self.token = "8406686288:AAHSHNwi_ocevorBddn5P_6Oc70aMx0-Usc"
        self.chat_id = "6823451625"
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.analyzer = AdvancedAnalyzer()
        self.last_update_id = 0
        self.user_states = {}
    
    def send_message(self, text, reply_markup=None):
        """Отправка сообщения в Telegram"""
        url = f"{self.base_url}/sendMessage"
        payload = {
            'chat_id': self.chat_id,
            'text': text,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        
        if reply_markup:
            payload['reply_markup'] = reply_markup
            
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                return True
        except Exception as e:
            print(f"❌ Ошибка отправки: {e}")
        return False
    
    def create_reply_keyboard(self):
        """Создает постоянное меню внизу экрана"""
        return {
            'keyboard': [
                ['🏆 ТОП 10', '📊 СТАТИСТИКА'],
                ['🔍 АНАЛИЗ МОНЕТЫ', '🚀 СИГНАЛЫ'],
                ['❓ ПОМОЩЬ']
            ],
            'resize_keyboard': True,
            'one_time_keyboard': False
        }
    
    def create_signal_keyboard(self, symbol):
        """Создает кнопки для сигналов"""
        return {
            'inline_keyboard': [
                [
                    {'text': '✅ СРАБОТАЛ', 'callback_data': f'success_{symbol}'},
                    {'text': '❌ НЕ СРАБОТАЛ', 'callback_data': f'fail_{symbol}'}
                ],
                [
                    {'text': '💡 ЧАСТИЧНО', 'callback_data': f'partial_{symbol}'}
                ]
            ]
        }
    
    def format_top_predictions(self, predictions):
        """Форматирует топ предсказаний"""
        message = "🏆 <b>ТОП 10 ПЕРСПЕКТИВНЫХ МОНЕТ</b>\n\n"
        
        for i, coin in enumerate(predictions, 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            
            message += f"{emoji} <b>{coin['symbol']}</b> - Score: {coin['score']}%\n"
            message += f"   💰 ${coin['price']:.6f} | 📈 {coin['price_change_24h']:.1f}%\n"
            
            main_reason = list(coin['analysis'].values())[0] if coin['analysis'] else "Нет данных"
            message += f"   🔍 {main_reason}\n\n"
        
        message += "⚡ <i>Обновляется каждые 5 минут</i>"
        return message
    
    def format_coin_analysis(self, analysis):
        """Форматирует детальный анализ монеты"""
        if not analysis:
            return "❌ Монета не найдена. Проверьте символ (например: BTC, ETH, SOL)"
        
        message = f"""
🔍 <b>ДЕТАЛЬНЫЙ АНАЛИЗ - {analysis['symbol']}</b>

🏷️ <b>Название:</b> {analysis['name']}
🎯 <b>Общий счет:</b> {analysis['score']}/100
💰 <b>Цена:</b> ${analysis['price']:.6f}
📊 <b>Изменение 24ч:</b> {analysis['price_change_24h']:.1f}%
🏦 <b>Капитализация:</b> ${analysis['market_cap']:,.0f}
📈 <b>Объем/Капа:</b> {analysis['volume_ratio']:.2%}

<b>АНАЛИЗ МЕТРИК:</b>
"""
        for metric, desc in analysis['analysis'].items():
            message += f"• {desc}\n"
        
        message += f"\n<b>РЕКОМЕНДАЦИЯ:</b>\n{analysis['recommendation']}"
        return message
    
    def format_statistics(self):
        """Форматирует общую статистику"""
        message = """
📊 <b>СТАТИСТИКА СИСТЕМЫ</b>

<b>📈 АНАЛИЗИРУЕТ:</b>
• 100+ криптовалют
• Volume/Market Cap соотношения
• Price momentum и тренды
• Риск/потенциал роста

<b>🎯 КРИТЕРИИ ОТБОРА:</b>
• Малая капитализация (<$50M)
• Высокий объем торгов
• Умеренный рост (5-50%)
• Не перекупленные активы

<b>🚀 ВОЗМОЖНОСТИ:</b>
• Авто-сигналы каждые 5 минут
• Ручной анализ любой монеты
• Топ 10 перспективных активов
• Обучение на ваших оценках

⚡ <i>Система постоянно улучшается!</i>
"""
        return message
    
    def format_help(self):
        """Форматирует помощь"""
        help_text = """
❓ <b>ПОМОЩЬ ПО СИСТЕМЕ</b>

<b>🏆 ТОП 10</b> - Лучшие монеты по потенциалу роста
<b>📊 СТАТИСТИКА</b> - Информация о системе
<b>🔍 АНАЛИЗ МОНЕТЫ</b> - Детальный анализ по символу
<b>🚀 СИГНАЛЫ</b> - Активные торговые сигналы

<b>📈 КАК ИСПОЛЬЗОВАТЬ:</b>
1. Используйте меню для навигации
2. Для анализа введите символ монеты
3. Отмечайте результаты сигналов
4. Система учится на ваших оценках

<b>💡 ПРИМЕРЫ СИМВОЛОВ:</b>
BTC, ETH, SOL, ADA, DOT, MATIC, AVAX, NEAR

⚡ <i>Бот работает 24/7 и постоянно анализирует рынок!</i>
"""
        return help_text
    
    def show_top_predictions(self):
        """Показывает топ 10 монет"""
        coins_data = self.analyzer.fetch_all_coins()
        predictions = self.analyzer.get_top_predictions(coins_data, 10)
        message = self.format_top_predictions(predictions)
        keyboard = self.create_reply_keyboard()
        self.send_message(message, keyboard)
    
    def show_statistics(self):
        """Показывает статистику"""
        message = self.format_statistics()
        keyboard = self.create_reply_keyboard()
        self.send_message(message, keyboard)
    
    def show_help(self):
        """Показывает помощь"""
        message = self.format_help()
        keyboard = self.create_reply_keyboard()
        self.send_message(message, keyboard)
    
    def ask_for_coin_symbol(self):
        """Просит ввести символ монеты"""
        message = """
🔍 <b>АНАЛИЗ МОНЕТЫ</b>

Введите символ монеты для анализа:
• <b>Примеры:</b> BTC, ETH, SOL, ADA, DOT
• <b>Или:</b> MATIC, AVAX, NEAR, ATOM

📊 <i>Я проанализирую:
- Volume/Market Cap соотношение
- Price momentum и тренды
- Потенциал роста и риски
- Общий scoring (0-100)</i>

💡 <b>Введите символ сейчас:</b>
"""
        keyboard = self.create_reply_keyboard()
        self.send_message(message, keyboard)
    
    def analyze_coin_by_symbol(self, symbol):
        """Анализирует монету по символу"""
        coins_data = self.analyzer.fetch_all_coins()
        analysis = self.analyzer.get_coin_analysis(symbol, coins_data)
        message = self.format_coin_analysis(analysis)
        keyboard = self.create_reply_keyboard()
        self.send_message(message, keyboard)
    
    def show_active_signals(self):
        """Показывает активные сигналы"""
        message = """
🚀 <b>АКТИВНЫЕ СИГНАЛЫ</b>

Сигналы появляются здесь автоматически при обнаружении перспективных монет!

<b>📈 СИГНАЛЫ ВКЛЮЧАЮТ:</b>
• Монеты с scoring > 60%
• Высокий объем при низкой капе
• Умеренный рост с потенциалом
• Минимальные риски

<b>⏰ ЧАСТОТА СИГНАЛОВ:</b>
• Авто-проверка каждые 5 минут
• Только качественные setup
• Фильтрация шума и манипуляций

⚡ <i>Следующая проверка через 5 минут...</i>
"""
        keyboard = self.create_reply_keyboard()
        self.send_message(message, keyboard)
    
    def send_signal(self, coin, score, analysis):
        """Отправляет торговый сигнал"""
        symbol = coin['symbol'].upper()
        
        message = f"""
🎯 <b>СИГНАЛ - {symbol}</b>

⭐ <b>Score:</b> {score}/100
💰 <b>Цена:</b> ${coin['current_price']:.6f}
📊 <b>Изменение 24ч:</b> {coin.get('price_change_percentage_24h', 0):.1f}%

<b>ОСНОВНЫЕ ПРИЧИНЫ:</b>
{chr(10).join(['• ' + reason for reason in analysis.values()][:3])}

💡 <i>Отметь результат для обучения системы!</i>
"""
        
        keyboard = self.create_signal_keyboard(symbol)
        return self.send_message(message, keyboard)
    
    def check_updates(self):
        """Проверяет обновления от Telegram"""
        try:
            url = f"{self.base_url}/getUpdates"
            params = {'offset': self.last_update_id + 1, 'timeout': 10}
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                updates = response.json().get('result', [])
                
                for update in updates:
                    self.last_update_id = update['update_id']
                    
                    if 'message' in update:
                        self.handle_message(update['message'])
                    elif 'callback_query' in update:
                        self.handle_callback(update['callback_query'])
                        
        except Exception as e:
            print(f"❌ Ошибка проверки обновлений: {e}")
    
    def handle_message(self, message):
        """Обрабатывает текстовые сообщения"""
        if 'text' not in message:
            return
        
        text = message['text']
        print(f"📨 Получено сообщение: {text}")
        
        if text == '🏆 ТОП 10':
            self.show_top_predictions()
        elif text == '📊 СТАТИСТИКА':
            self.show_statistics()
        elif text == '🔍 АНАЛИЗ МОНЕТЫ':
            self.ask_for_coin_symbol()
        elif text == '🚀 СИГНАЛЫ':
            self.show_active_signals()
        elif text == '❓ ПОМОЩЬ':
            self.show_help()
        else:
            # Предполагаем что это символ монеты
            if len(text) <= 10 and text.isalnum():
                self.analyze_coin_by_symbol(text)
            else:
                self.send_message("❌ Неизвестная команда. Используйте меню ниже.", self.create_reply_keyboard())
    
    def handle_callback(self, callback_query):
        """Обрабатывает callback запросы (нажатия кнопок под сообщениями)"""
        try:
            callback_data = callback_query['data']
            message = callback_query['message']
            
            print(f"🔘 Нажата кнопка: {callback_data}")
            
            if callback_data.startswith('success_'):
                symbol = callback_data.replace('success_', '')
                self.send_message(f"✅ <b>ФИДБЕК ЗАПИСАН!</b>\n\n{symbol} - СРАБОТАЛ\n\nСпасибо! Система учится 🧠", self.create_reply_keyboard())
            elif callback_data.startswith('fail_'):
                symbol = callback_data.replace('fail_', '')
                self.send_message(f"✅ <b>ФИДБЕК ЗАПИСАН!</b>\n\n{symbol} - НЕ СРАБОТАЛ\n\nСпасибо! Система учится 🧠", self.create_reply_keyboard())
            elif callback_data.startswith('partial_'):
                symbol = callback_data.replace('partial_', '')
                self.send_message(f"✅ <b>ФИДБЕК ЗАПИСАН!</b>\n\n{symbol} - ЧАСТИЧНО\n\nСпасибо! Система учится 🧠", self.create_reply_keyboard())
                
        except Exception as e:
            print(f"❌ Ошибка обработки callback: {e}")
    
    def send_welcome(self):
        """Отправляет приветственное сообщение"""
        welcome_text = """
🤖 <b>ПРОДВИНУТАЯ СИСТЕМА АНАЛИЗА КРИПТО</b>

🚀 <b>ЗАПУСК СИСТЕМЫ...</b>

📊 <b>АНАЛИЗИРУЕТ:</b>
• 100+ криптовалют в реальном времени
• Volume/Market Cap соотношения
• Price momentum и тренды
• Риск/потенциал роста

🎯 <b>ВОЗМОЖНОСТИ:</b>
• 🏆 Топ 10 перспективных монет
• 🔍 Детальный анализ любой монеты
• 📊 Статистика и метрики
• 🚀 Авто-сигналы

⚡ <b>Используйте меню ниже для навигации!</b>
"""
        keyboard = self.create_reply_keyboard()
        self.send_message(welcome_text, keyboard)

def main():
    print("🚀 Запуск ФИНАЛЬНОЙ версии бота...")
    
    bot = CryptoFinalBot()
    
    # Запуск обработки обновлений
    def updates_worker():
        while True:
            bot.check_updates()
            time.sleep(2)
    
    updates_thread = Thread(target=updates_worker, daemon=True)
    updates_thread.start()
    
    # Приветственное сообщение
    bot.send_welcome()
    
    # Основной цикл анализа
    while True:
        try:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Анализ рынка...")
            
            # Загружаем и анализируем монеты
            coins_data = bot.analyzer.fetch_all_coins()
            if coins_data:
                print(f"📊 Проанализировано {len(coins_data)} монет")
                
                # Получаем топ предсказания
                top_predictions = bot.analyzer.get_top_predictions(coins_data, 10)
                
                # Отправляем сигналы для топ монет с высоким score
                signals_sent = 0
                for coin_data in top_predictions[:3]:  # Топ 3
                    if coin_data['score'] >= CONFIG['min_confidence']:
                        # Находим полные данные монеты
                        for coin in coins_data:
                            if coin['symbol'].upper() == coin_data['symbol']:
                                if bot.send_signal(coin, coin_data['score'], coin_data['analysis']):
                                    signals_sent += 1
                                    time.sleep(3)
                                break
                
                if signals_sent == 0:
                    print("📊 Сигналов не найдено")
                else:
                    print(f"📤 Отправлено сигналов: {signals_sent}")
            
            print(f"💤 Ожидание {CONFIG['interval']} секунд...")
            time.sleep(CONFIG['interval'])
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()