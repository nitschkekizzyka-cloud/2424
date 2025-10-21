# crypto_final_bot.py - ТОП-100 + НОВОСТИ + АВТО-АЛЕРТЫ
import requests
import time
import json
import re
import pandas as pd
from datetime import datetime
from threading import Thread, Lock
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

CONFIG = {
    'database_path': 'crypto_final.db',
    'interval': 5 * 60,
    'min_confidence': 60,
    'news_check_interval': 10 * 60
}

EXCLUDE_COINS = ['usdt', 'usdc', 'busd', 'dai', 'tusd', 'ust', 'fdusd', 'pyusd']

class NewsMonitor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.last_news = {}
    
    def get_crypto_news(self):
        """Получает последние крипто-новости"""
        try:
            url = "https://api.coingecko.com/api/v3/news"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                news_data = response.json()
                return self.process_news(news_data.get('data', []))
        except Exception as e:
            logging.error(f"❌ Ошибка загрузки новостей: {e}")
        
        return []
    
    def process_news(self, news_items):
        """Обрабатывает новости и извлекает монеты"""
        processed_news = []
        
        for news in news_items[:10]:
            title = news.get('title', '')
            description = news.get('description', '')
            url = news.get('url', '')
            
            mentioned_coins = self.extract_coins_from_text(title + " " + description)
            
            if mentioned_coins:
                news_item = {
                    'title': title,
                    'description': description[:200] + "..." if len(description) > 200 else description,
                    'url': url,
                    'coins': mentioned_coins,
                    'timestamp': datetime.now()
                }
                processed_news.append(news_item)
        
        return processed_news
    
    def extract_coins_from_text(self, text):
        """Извлекает упоминания монет из текста"""
        text_upper = text.upper()
        found_coins = []
        
        popular_coins = [
            'BTC', 'ETH', 'BNB', 'XRP', 'ADA', 'DOGE', 'SOL', 'DOT', 'MATIC', 
            'AVAX', 'LINK', 'ATOM', 'XLM', 'ALGO', 'NEAR', 'FTM', 'SAND', 
            'MANA', 'GALA', 'APE', 'GMT', 'APT', 'ARB', 'OP', 'SUI', 'RUNE',
            'PEPE', 'SHIB', 'FLOKI', 'BONK', 'WIF', 'DOGE', 'MEME'
        ]
        
        for coin in popular_coins:
            if coin in text_upper:
                found_coins.append(coin)
        
        return list(set(found_coins))
    
    def check_new_news(self):
        """Проверяет новые новости и возвращает непрочитанные"""
        current_news = self.get_crypto_news()
        new_news = []
        
        for news in current_news:
            news_id = f"{news['title']}_{news['timestamp'].strftime('%Y%m%d%H%M')}"
            if news_id not in self.last_news:
                new_news.append(news)
                self.last_news[news_id] = news['timestamp']
        
        # Очищаем старые новости
        current_time = datetime.now()
        expired_news = [
            news_id for news_id, timestamp in self.last_news.items()
            if (current_time - timestamp).total_seconds() > 24 * 3600
        ]
        for news_id in expired_news:
            del self.last_news[news_id]
        
        return new_news

class AdvancedAnalyzer:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.news_monitor = NewsMonitor()
    
    def fetch_top_coins(self):
        """Загружает топ-100 монет"""
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 100,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h,7d"
        }
        
        try:
            logging.info("🔄 Загрузка данных с CoinGecko...")
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code == 200:
                coins = response.json()
                filtered_coins = [
                    coin for coin in coins 
                    if coin['symbol'].lower() not in EXCLUDE_COINS
                ]
                logging.info(f"✅ Успешно загружено {len(filtered_coins)} монет")
                return filtered_coins
            else:
                logging.error(f"❌ Ошибка API: {response.status_code}")
        except Exception as e:
            logging.error(f"❌ Ошибка загрузки монет: {e}")
        return []
    
    def search_coin(self, symbol):
        """Ищет монету по символу"""
        symbol = symbol.upper().strip()
        logging.info(f"🔍 Поиск монеты: {symbol}")
        
        # Сначала ищем в топ-100
        top_coins = self.fetch_top_coins()
        for coin in top_coins:
            if coin['symbol'].upper() == symbol:
                logging.info(f"✅ Найдена монета в топ-100: {symbol}")
                return coin
        
        # Если не нашли в топ-100, пробуем через поиск CoinGecko
        try:
            search_url = f"https://api.coingecko.com/api/v3/search?query={symbol}"
            search_response = self.session.get(search_url, timeout=10)
            
            if search_response.status_code == 200:
                search_data = search_response.json()
                coins_list = search_data.get('coins', [])
                
                if coins_list:
                    coin_id = coins_list[0]['id']
                    coin_url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
                    coin_response = self.session.get(coin_url, timeout=10)
                    
                    if coin_response.status_code == 200:
                        coin_data = coin_response.json()
                        if 'market_data' in coin_data:
                            logging.info(f"✅ Найдена монета через поиск: {symbol}")
                            return {
                                'id': coin_data['id'],
                                'symbol': coin_data['symbol'].upper(),
                                'name': coin_data['name'],
                                'current_price': coin_data['market_data']['current_price']['usd'],
                                'market_cap': coin_data['market_data']['market_cap']['usd'],
                                'total_volume': coin_data['market_data']['total_volume']['usd'],
                                'price_change_percentage_24h': coin_data['market_data']['price_change_percentage_24h']
                            }
        except Exception as e:
            logging.error(f"❌ Ошибка поиска монеты {symbol}: {e}")
        
        logging.warning(f"⚠️ Монета не найдена: {symbol}")
        return None
    
    def calculate_coin_score(self, coin):
        """Расчитывает комплексный счет монеты (0-100)"""
        score = 0
        analysis = {}
        
        try:
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
            price_change_24h = coin.get('price_change_percentage_24h', 0) or 0
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
            if market_cap < 50000000:
                score += 20
                analysis['market_cap'] = "🏦 Малая капа - высокий потенциал"
            elif market_cap < 200000000:
                score += 15
                analysis['market_cap'] = "🏦 Средняя капа"
            
            # 4. Risk Adjustment
            if price_change_24h > 100:
                score -= 15
                analysis['risk'] = "⚠️ Перекуплена - высокий риск"
                
        except Exception as e:
            logging.error(f"❌ Ошибка расчета score: {e}")
        
        return max(0, min(100, score)), analysis
    
    def get_top_predictions(self, coins_data, top_n=10):
        """Возвращает топ монет по предсказательной силе"""
        predictions = []
        
        for coin in coins_data:
            try:
                score, analysis = self.calculate_coin_score(coin)
                predictions.append({
                    'symbol': coin['symbol'].upper(),
                    'name': coin['name'],
                    'score': score,
                    'price': coin['current_price'],
                    'price_change_24h': coin.get('price_change_percentage_24h', 0) or 0,
                    'market_cap': coin['market_cap'],
                    'volume': coin['total_volume'],
                    'analysis': analysis
                })
            except Exception as e:
                logging.error(f"❌ Ошибка анализа монеты {coin.get('symbol', 'unknown')}: {e}")
                continue
        
        predictions.sort(key=lambda x: x['score'], reverse=True)
        return predictions[:top_n]
    
    def get_coin_analysis(self, symbol):
        """Детальный анализ конкретной монеты"""
        coin_data = self.search_coin(symbol)
        
        if coin_data:
            score, analysis = self.calculate_coin_score(coin_data)
            return {
                'symbol': symbol.upper(),
                'name': coin_data['name'],
                'score': score,
                'price': coin_data['current_price'],
                'price_change_24h': coin_data.get('price_change_percentage_24h', 0) or 0,
                'market_cap': coin_data['market_cap'],
                'volume': coin_data['total_volume'],
                'volume_ratio': coin_data['total_volume'] / coin_data['market_cap'] if coin_data['market_cap'] > 0 else 0,
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
        self.is_processing = False
        self.user_states = {}
        self.last_manual_update = 0
        self.cached_predictions = None
        self.last_successful_update = None
    
    def send_message(self, text, reply_markup=None):
        """Отправка сообщения в Telegram"""
        if self.is_processing:
            return False
            
        self.is_processing = True
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
                logging.info("✅ Сообщение отправлено")
                return True
            else:
                logging.error(f"❌ Ошибка отправки: {response.status_code}")
        except Exception as e:
            logging.error(f"❌ Ошибка отправки: {e}")
        finally:
            self.is_processing = False
        return False
    
    def create_reply_keyboard(self):
        """Создает постоянное меню внизу экрана"""
        return {
            'keyboard': [
                ['🏆 ТОП 10', '🔄 ОБНОВИТЬ'],
                ['🔍 АНАЛИЗ МОНЕТЫ', '🚀 СИГНАЛЫ'],
                ['📰 КРИПТО-НОВОСТИ', '❓ ПОМОЩЬ']
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
    
    def format_news_alert(self, news_item):
        """Форматирует новостной алерт"""
        coins_text = ", ".join(news_item['coins'])
        
        message = f"""
📰 <b>НОВОСТНОЙ АЛЕРТ!</b>

🏷️ <b>Заголовок:</b> {news_item['title']}
📝 <b>Описание:</b> {news_item['description']}
💰 <b>Упоминания:</b> {coins_text}

🔗 <a href="{news_item['url']}">Читать полностью</a>

💡 <i>Проверьте упомянутые монеты!</i>
"""
        return message
    
    def format_top_predictions(self, predictions, show_cache_info=False, update_time=None):
        """Форматирует топ предсказаний"""
        if not predictions:
            return "📊 <b>ТОП 10 ПЕРСПЕКТИВНЫХ МОНЕТ</b>\n\nНа данный момент нет данных для анализа. Попробуйте позже."
        
        message = "🏆 <b>ТОП 10 ПЕРСПЕКТИВНЫХ МОНЕТ</b>\n\n"
        
        for i, coin in enumerate(predictions, 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            
            # Форматируем цену
            price = coin['price']
            if price is None:
                price_str = "N/A"
            elif price < 0.001:
                price_str = f"${price:.8f}"
            elif price < 1:
                price_str = f"${price:.6f}"
            else:
                price_str = f"${price:.2f}"
            
            message += f"{emoji} <b>{coin['symbol']}</b> - Score: {coin['score']}%\n"
            message += f"   💰 {price_str} | 📈 {coin['price_change_24h']:.1f}%\n"
            
            # Получаем первый анализ для отображения
            if coin['analysis']:
                main_reason = list(coin['analysis'].values())[0]
                message += f"   🔍 {main_reason}\n"
            else:
                message += f"   🔍 Нет данных анализа\n"
            
            message += "\n"
        
        if show_cache_info and update_time:
            time_diff = datetime.now() - update_time
            minutes_ago = int(time_diff.total_seconds() / 60)
            message += f"💾 <i>Данные актуальны на {update_time.strftime('%H:%M:%S')} ({minutes_ago} мин. назад)</i>\n"
        else:
            message += "⚡ <i>Данные обновлены только что</i>\n"
            
        message += "🔄 <i>Авто-обновление каждые 5 минут</i>"
        return message
    
    def format_coin_analysis(self, analysis):
        """Форматирует детальный анализ монеты"""
        if not analysis:
            return "❌ Монета не найдена. Проверьте символ (например: BTC, ETH, SOL, NEAR)"
        
        # Форматируем цену
        price = analysis['price']
        if price is None:
            price_str = "N/A"
        elif price < 0.001:
            price_str = f"${price:.8f}"
        elif price < 1:
            price_str = f"${price:.6f}"
        else:
            price_str = f"${price:.2f}"
        
        message = f"""
🔍 <b>ДЕТАЛЬНЫЙ АНАЛИЗ - {analysis['symbol']}</b>

🏷️ <b>Название:</b> {analysis['name']}
🎯 <b>Общий счет:</b> {analysis['score']}/100
💰 <b>Цена:</b> {price_str}
📊 <b>Изменение 24ч:</b> {analysis['price_change_24h']:.1f}%
🏦 <b>Капитализация:</b> ${analysis['market_cap']:,.0f}
📈 <b>Объем/Капа:</b> {analysis['volume_ratio']:.2%}

<b>АНАЛИЗ МЕТРИК:</b>
"""
        if analysis['analysis']:
            for metric, desc in analysis['analysis'].items():
                message += f"• {desc}\n"
        else:
            message += "• Нет данных анализа\n"
        
        message += f"\n<b>РЕКОМЕНДАЦИЯ:</b>\n{analysis['recommendation']}"
        return message
    
    def format_statistics(self):
        """Форматирует общую статистику"""
        message = """
📊 <b>СТАТИСТИКА СИСТЕМЫ</b>

<b>📈 АНАЛИЗИРУЕТ:</b>
• Топ-100 криптовалют
• Volume/Market Cap соотношения
• Price momentum и тренды
• Крипто-новости и алерты

<b>🎯 КРИТЕРИИ ОТБОРА:</b>
• Малая капитализация (<$50M)
• Высокий объем торгов
• Умеренный рост (5-50%)
• Упоминания в новостях

<b>🚀 ВОЗМОЖНОСТИ:</b>
• Авто-сигналы каждые 5 минут
• Ручной анализ любой монеты
• Новостные алерты
• Топ 10 перспективных активов

⚡ <i>Система постоянно улучшается!</i>
"""
        return message
    
    def format_help(self):
        """Форматирует помощь"""
        help_text = """
❓ <b>ПОМОЩЬ ПО СИСТЕМЕ</b>

<b>🏆 ТОП 10</b> - Лучшие монеты по потенциалу роста
<b>🔄 ОБНОВИТЬ</b> - Принудительное обновление данных (раз в 30 сек)
<b>🔍 АНАЛИЗ МОНЕТЫ</b> - Детальный анализ по символу
<b>🚀 СИГНАЛЫ</b> - Активные торговые сигналы
<b>📰 КРИПТО-НОВОСТИ</b> - Свежие новости с упоминаниями монет

<b>📈 КАК ИСПОЛЬЗОВАТЬ:</b>
1. Используйте меню для навигации
2. Для анализа введите символ монеты
3. Отмечайте результаты сигналов
4. Следите за новостными алерами

<b>💡 ПРИМЕРЫ СИМВОЛОВ:</b>
BTC, ETH, SOL, ADA, DOT, MATIC, AVAX, NEAR

⚡ <i>Бот работает 24/7 и постоянно анализирует рынок!</i>
"""
        return help_text
    
    def handle_manual_update(self):
        """Обрабатывает ручное обновление с таймером"""
        current_time = time.time()
        time_since_last = current_time - self.last_manual_update
        
        if time_since_last < 30:
            seconds_left = 30 - int(time_since_last)
            return f"⏰ Обновить можно через {seconds_left} сек."
        else:
            self.last_manual_update = current_time
            return self.show_top_predictions(force_update=True)
    
    def show_top_predictions(self, force_update=False):
        """Показывает топ 10 монет"""
        # Если есть кеш и не принудительное обновление - используем кеш
        if self.cached_predictions and not force_update:
            message = self.format_top_predictions(
                self.cached_predictions, 
                show_cache_info=True,
                update_time=self.last_successful_update
            )
            keyboard = self.create_reply_keyboard()
            self.send_message(message, keyboard)
            return
        
        logging.info("🔄 Получение данных для ТОП 10...")
        coins_data = self.analyzer.fetch_top_coins()
        if coins_data:
            logging.info(f"📊 Найдено {len(coins_data)} монет для анализа")
            predictions = self.analyzer.get_top_predictions(coins_data, 10)
            self.cached_predictions = predictions
            self.last_successful_update = datetime.now()
            message = self.format_top_predictions(predictions)
            if force_update:
                message = message.replace("Данные обновлены только что", "✅ <b>Данные обновлены!</b>")
            keyboard = self.create_reply_keyboard()
            self.send_message(message, keyboard)
        else:
            # Если API недоступно, показываем кеш или ошибку
            if self.cached_predictions:
                message = self.format_top_predictions(
                    self.cached_predictions,
                    show_cache_info=True,
                    update_time=self.last_successful_update
                )
                message += "\n\n⚠️ <i>API временно недоступно. Показаны последние сохраненные данные</i>"
                keyboard = self.create_reply_keyboard()
                self.send_message(message, keyboard)
            else:
                self.send_message("❌ Не удалось получить данные с CoinGecko. Попробуйте позже.", self.create_reply_keyboard())
    
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
    
    def show_crypto_news(self):
        """Показывает последние крипто-новости"""
        news_items = self.analyzer.news_monitor.get_crypto_news()
        
        if not news_items:
            message = "📰 <b>ПОСЛЕДНИЕ НОВОСТИ</b>\n\nНа данный момент новостей нет. Проверка каждые 10 минут! 🔄"
            keyboard = self.create_reply_keyboard()
            self.send_message(message, keyboard)
            return
        
        for news in news_items[:3]:
            message = self.format_news_alert(news)
            keyboard = self.create_reply_keyboard()
            self.send_message(message, keyboard)
            time.sleep(1)
    
    def ask_for_coin_symbol(self):
        """Просит ввести символ монеты"""
        message = """
🔍 <b>АНАЛИЗ МОНЕТЫ</b>

Введите символ монеты для анализа:
• <b>Примеры:</b> BTC, ETH, SOL, ADA, DOT
• <b>Или:</b> MATIC, AVAX, NEAR, APT, ARB
• <b>Или ЛЮБАЯ другая монета!</b>

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
        logging.info(f"🔍 Анализ монеты: {symbol}")
        analysis = self.analyzer.get_coin_analysis(symbol)
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
• Упоминания в новостях

<b>⏰ ЧАСТОТА СИГНАЛОВ:</b>
• Авто-проверка каждые 5 минут
• Новостные алерты каждые 10 минут
• Только качественные setup

⚡ <i>Следующая проверка через 5 минут...</i>
"""
        keyboard = self.create_reply_keyboard()
        self.send_message(message, keyboard)
    
    def send_signal(self, coin, score, analysis):
        """Отправляет торговый сигнал"""
        symbol = coin['symbol'].upper()
        
        # Форматируем цену
        price = coin['current_price']
        if price is None:
            price_str = "N/A"
        elif price < 0.001:
            price_str = f"${price:.8f}"
        elif price < 1:
            price_str = f"${price:.6f}"
        else:
            price_str = f"${price:.2f}"
        
        message = f"""
🎯 <b>СИГНАЛ - {symbol}</b>

⭐ <b>Score:</b> {score}/100
💰 <b>Цена:</b> {price_str}
📊 <b>Изменение 24ч:</b> {coin.get('price_change_percentage_24h', 0):.1f}%

<b>ОСНОВНЫЕ ПРИЧИНЫ:</b>
"""
        if analysis:
            for reason in list(analysis.values())[:3]:
                message += f"• {reason}\n"
        else:
            message += "• Нет данных анализа\n"
        
        message += "\n💡 <i>Отметь результат для обучения системы!</i>"
        
        keyboard = self.create_signal_keyboard(symbol)
        return self.send_message(message, keyboard)
    
    def send_news_alerts(self):
        """Отправляет новостные алерты"""
        new_news = self.analyzer.news_monitor.check_new_news()
        
        for news in new_news:
            message = self.format_news_alert(news)
            keyboard = self.create_reply_keyboard()
            self.send_message(message, keyboard)
            time.sleep(1)
    
    def check_updates(self):
        """Проверяет обновления от Telegram"""
        try:
            url = f"{self.base_url}/getUpdates"
            params = {'offset': self.last_update_id + 1, 'timeout': 5}
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                updates = response.json().get('result', [])
                
                for update in updates:
                    self.last_update_id = update['update_id']
                    
                    if 'message' in update:
                        self.handle_message(update['message'])
                    elif 'callback_query' in update:
                        self.handle_callback(update['callback_query'])
                        
        except Exception as e:
            logging.error(f"❌ Ошибка проверки обновлений: {e}")
    
    def handle_message(self, message):
        """Обрабатывает текстовые сообщения"""
        if 'text' not in message:
            return
        
        text = message['text'].strip()
        logging.info(f"📨 Получено сообщение: {text}")
        
        # Обработка команд меню
        if text == '🏆 ТОП 10':
            self.show_top_predictions()
        elif text == '🔄 ОБНОВИТЬ':
            result = self.handle_manual_update()
            if isinstance(result, str):
                self.send_message(result, self.create_reply_keyboard())
        elif text == '📊 СТАТИСТИКА':
            self.show_statistics()
        elif text == '🔍 АНАЛИЗ МОНЕТЫ':
            self.ask_for_coin_symbol()
        elif text == '🚀 СИГНАЛЫ':
            self.show_active_signals()
        elif text == '📰 КРИПТО-НОВОСТИ':
            self.show_crypto_news()
        elif text == '❓ ПОМОЩЬ':
            self.show_help()
        else:
            # Предполагаем что это символ монеты (3-10 символов, только буквы/цифры)
            if 2 <= len(text) <= 10 and text.replace(' ', '').isalnum():
                self.analyze_coin_by_symbol(text)
            else:
                self.send_message("❌ Неизвестная команда. Используйте меню ниже.", self.create_reply_keyboard())
    
    def handle_callback(self, callback_query):
        """Обрабатывает callback запросы"""
        try:
            callback_data = callback_query['data']
            message = callback_query['message']
            
            logging.info(f"🔘 Нажата кнопка: {callback_data}")
            
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
            logging.error(f"❌ Ошибка обработки callback: {e}")
    
    def send_welcome(self):
        """Отправляет приветственное сообщение"""
        welcome_text = """
🤖 <b>ПРОДВИНУТАЯ СИСТЕМА АНАЛИЗА КРИПТО</b>

🚀 <b>СИСТЕМА ЗАПУЩЕНА</b>

📊 <b>АНАЛИЗИРУЕТ:</b>
• Топ-100 криптовалют
• Volume/Market Cap соотношения
• Price momentum и тренды
• Крипто-новости в реальном времени

🎯 <b>ВОЗМОЖНОСТИ:</b>
• 🏆 Топ 10 перспективных монет
• 🔍 Детальный анализ любой монеты
• 📰 Новостные алерты с упоминаниями
• 🚀 Авто-сигналы

⚡ <b>Используйте меню ниже для навигации!</b>
"""
        keyboard = self.create_reply_keyboard()
        self.send_message(welcome_text, keyboard)

def main():
    logging.info("🚀 Запуск ФИНАЛЬНОЙ версии бота с новостями...")
    
    bot = CryptoFinalBot()
    
    # Запуск обработки обновлений
    def updates_worker():
        while True:
            try:
                bot.check_updates()
                time.sleep(1)
            except Exception as e:
                logging.error(f"❌ Ошибка в updates_worker: {e}")
                time.sleep(5)
    
    updates_thread = Thread(target=updates_worker, daemon=True)
    updates_thread.start()
    
    # Приветственное сообщение
    time.sleep(2)
    bot.send_welcome()
    
    last_news_check = time.time()
    last_analysis_check = time.time()
    
    # Основной цикл анализа
    while True:
        try:
            current_time = time.time()
            logging.info(f"\n[{datetime.now().strftime('%H:%M:%S')}] Анализ рынка...")
            
            # Загружаем и анализируем монеты каждые 5 минут
            if current_time - last_analysis_check > CONFIG['interval']:
                coins_data = bot.analyzer.fetch_top_coins()
                if coins_data:
                    logging.info(f"📊 Проанализировано {len(coins_data)} монет")
                    # Обновляем кеш при авто-обновлении
                    top_predictions = bot.analyzer.get_top_predictions(coins_data, 10)
                    bot.cached_predictions = top_predictions
                    bot.last
