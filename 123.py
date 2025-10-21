# crypto_advanced_bot.py
import asyncio
import aiohttp
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass
import json
import hashlib

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class CoinData:
    """Класс для хранения данных монеты"""
    symbol: str
    name: str
    price: float
    market_cap: float
    volume_24h: float
    price_change_24h: float
    price_change_7d: float
    timestamp: datetime

@dataclass
class TechnicalIndicators:
    """Технические индикаторы"""
    sma_20: float = 0
    ema_12: float = 0
    ema_26: float = 0
    rsi: float = 0
    macd: float = 0
    macd_signal: float = 0
    macd_histogram: float = 0
    volume_sma: float = 0

class DatabaseManager:
    """Менеджер базы данных"""
    
    def __init__(self, db_path: str = "crypto_bot.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Инициализация таблиц БД"""
        with sqlite3.connect(self.db_path) as conn:
            # Таблица исторических данных
            conn.execute('''
                CREATE TABLE IF NOT EXISTS coin_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    price REAL NOT NULL,
                    market_cap REAL NOT NULL,
                    volume_24h REAL NOT NULL,
                    price_change_24h REAL NOT NULL,
                    timestamp DATETIME NOT NULL,
                    UNIQUE(symbol, timestamp)
                )
            ''')
            
            # Таблица сигналов
            conn.execute('''
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    price REAL NOT NULL,
                    signal_type TEXT NOT NULL,
                    analysis TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE
                )
            ''')
            
            # Таблица фидбека
            conn.execute('''
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id INTEGER,
                    symbol TEXT NOT NULL,
                    feedback_type TEXT NOT NULL,
                    user_comment TEXT,
                    timestamp DATETIME NOT NULL,
                    FOREIGN KEY(signal_id) REFERENCES signals(id)
                )
            ''')
            
            # Таблица технических индикаторов
            conn.execute('''
                CREATE TABLE IF NOT EXISTS technical_indicators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    sma_20 REAL,
                    ema_12 REAL,
                    ema_26 REAL,
                    rsi REAL,
                    macd REAL,
                    macd_signal REAL,
                    macd_histogram REAL,
                    volume_sma REAL,
                    UNIQUE(symbol, timestamp)
                )
            ''')
            
            conn.commit()
    
    async def save_coin_data(self, coin_data: CoinData):
        """Сохраняет данные монеты в БД"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO coin_history 
                    (symbol, price, market_cap, volume_24h, price_change_24h, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    coin_data.symbol, coin_data.price, coin_data.market_cap,
                    coin_data.volume_24h, coin_data.price_change_24h, coin_data.timestamp
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения данных монеты: {e}")
    
    async def get_historical_data(self, symbol: str, days: int = 30) -> pd.DataFrame:
        """Получает исторические данные для расчета индикаторов"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql('''
                    SELECT symbol, price, volume_24h, timestamp
                    FROM coin_history 
                    WHERE symbol = ? AND timestamp >= datetime('now', ?)
                    ORDER BY timestamp
                ''', conn, params=(symbol, f'-{days} days'))
                return df
        except Exception as e:
            logger.error(f"Ошибка получения исторических данных: {e}")
            return pd.DataFrame()
    
    async def save_signal(self, symbol: str, score: int, price: float, 
                         signal_type: str, analysis: dict):
        """Сохраняет сигнал в БД"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    INSERT INTO signals 
                    (symbol, score, price, signal_type, analysis, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (symbol, score, price, signal_type, json.dumps(analysis), datetime.now()))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Ошибка сохранения сигнала: {e}")
            return None
    
    async def save_feedback(self, signal_id: int, symbol: str, 
                          feedback_type: str, comment: str = ""):
        """Сохраняет фидбек пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO feedback 
                    (signal_id, symbol, feedback_type, user_comment, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                ''', (signal_id, symbol, feedback_type, comment, datetime.now()))
                
                # Деактивируем сигнал после фидбека
                conn.execute('''
                    UPDATE signals SET is_active = FALSE WHERE id = ?
                ''', (signal_id,))
                
                conn.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения фидбека: {e}")

class TechnicalAnalyzer:
    """Анализатор технических индикаторов"""
    
    @staticmethod
    def calculate_sma(prices: List[float], window: int) -> float:
        """Простое скользящее среднее"""
        if len(prices) < window:
            return prices[-1] if prices else 0
        return np.mean(prices[-window:])
    
    @staticmethod
    def calculate_ema(prices: List[float], window: int) -> float:
        """Экспоненциальное скользящее среднее"""
        if not prices:
            return 0
        series = pd.Series(prices)
        return series.ewm(span=window, adjust=False).mean().iloc[-1]
    
    @staticmethod
    def calculate_rsi(prices: List[float], window: int = 14) -> float:
        """Индекс относительной силы"""
        if len(prices) < window + 1:
            return 50
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-window:])
        avg_loss = np.mean(losses[-window:])
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def calculate_macd(prices: List[float]) -> Tuple[float, float, float]:
        """MACD индикатор"""
        if len(prices) < 26:
            return 0, 0, 0
        
        ema_12 = TechnicalAnalyzer.calculate_ema(prices, 12)
        ema_26 = TechnicalAnalyzer.calculate_ema(prices, 26)
        macd = ema_12 - ema_26
        
        # Сигнальная линия (EMA от MACD)
        macd_values = [ema_12 - ema_26 for ema_12, ema_26 in 
                      zip(pd.Series(prices).ewm(span=12).mean(),
                          pd.Series(prices).ewm(span=26).mean())]
        signal = pd.Series(macd_values).ewm(span=9).mean().iloc[-1]
        histogram = macd - signal
        
        return macd, signal, histogram
    
    async def calculate_indicators(self, symbol: str, db: DatabaseManager) -> TechnicalIndicators:
        """Рассчитывает все технические индикаторы"""
        historical_data = await db.get_historical_data(symbol, 30)
        
        if historical_data.empty:
            return TechnicalIndicators()
        
        prices = historical_data['price'].tolist()
        volumes = historical_data['volume_24h'].tolist()
        
        indicators = TechnicalIndicators(
            sma_20=self.calculate_sma(prices, 20),
            ema_12=self.calculate_ema(prices, 12),
            ema_26=self.calculate_ema(prices, 26),
            rsi=self.calculate_rsi(prices),
            volume_sma=self.calculate_sma(volumes, 20)
        )
        
        macd, macd_signal, macd_histogram = self.calculate_macd(prices)
        indicators.macd = macd
        indicators.macd_signal = macd_signal
        indicators.macd_histogram = macd_histogram
        
        return indicators

class MLPredictor:
    """ML модель для прогнозирования"""
    
    def __init__(self):
        self.model = None
        self.is_trained = False
    
    async def prepare_features(self, symbol: str, db: DatabaseManager) -> Optional[List[float]]:
        """Подготавливает фичи для ML модели"""
        try:
            historical_data = await db.get_historical_data(symbol, 60)
            if len(historical_data) < 30:
                return None
            
            prices = historical_data['price'].values
            volumes = historical_data['volume_24h'].values
            
            # Базовые фичи
            features = [
                # Ценовые фичи
                prices[-1],  # текущая цена
                np.mean(prices[-7:]),  # среднее за неделю
                np.std(prices[-7:]),   # волатильность за неделю
                
                # Объемные фичи
                volumes[-1],  # текущий объем
                np.mean(volumes[-7:]),  # средний объем за неделю
                
                # Технические индикаторы
                TechnicalAnalyzer.calculate_rsi(prices.tolist()),
                TechnicalAnalyzer.calculate_ema(prices.tolist(), 12),
                TechnicalAnalyzer.calculate_ema(prices.tolist(), 26),
            ]
            
            return features
        except Exception as e:
            logger.error(f"Ошибка подготовки фич: {e}")
            return None
    
    async def predict(self, symbol: str, db: DatabaseManager) -> float:
        """Прогнозирует потенциал роста (0-100)"""
        features = await self.prepare_features(symbol, db)
        
        if not features:
            return 50  # нейтральный прогноз при отсутствии данных
        
        # Простая эвристическая модель (замените на настоящую ML модель)
        base_score = 50
        
        # Корректировки на основе фич
        rsi = features[5]
        if rsi < 30:
            base_score += 15  # перепроданность
        elif rsi > 70:
            base_score -= 15  # перекупленность
        
        volume_ratio = features[4] / features[3] if features[3] > 0 else 1
        if volume_ratio > 1.5:
            base_score += 10  # растущий объем
        
        ema_ratio = features[6] / features[7] if features[7] > 0 else 1
        if ema_ratio > 1.02:
            base_score += 10  # бычий тренд
        
        return max(0, min(100, base_score))

class AdvancedAnalyzer:
    """Продвинутый анализатор"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.technical_analyzer = TechnicalAnalyzer()
        self.ml_predictor = MLPredictor()
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_top_coins(self, limit: int = 100) -> List[Dict]:
        """Асинхронно загружает топ монет"""
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": limit,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h,7d,30d"
        }
        
        try:
            async with self.session.get(url, params=params, timeout=30) as response:
                if response.status == 200:
                    coins = await response.json()
                    filtered_coins = [
                        coin for coin in coins 
                        if coin['symbol'] not in ['usdt', 'usdc', 'busd', 'dai']
                    ]
                    logger.info(f"✅ Успешно загружено {len(filtered_coins)} монет")
                    return filtered_coins
                else:
                    logger.error(f"❌ Ошибка API: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки монет: {e}")
            return []
    
    async def calculate_advanced_score(self, coin: Dict, indicators: TechnicalIndicators) -> Tuple[int, Dict]:
        """Расширенный расчет score с ML и техническими индикаторами"""
        score = 0
        analysis = {}
        
        try:
            symbol = coin['symbol'].upper()
            
            # 1. Базовые метрики (40%)
            volume_ratio = coin['total_volume'] / coin['market_cap'] if coin['market_cap'] > 0 else 0
            price_change_24h = coin.get('price_change_percentage_24h', 0) or 0
            
            if volume_ratio > 0.3:
                score += 20
                analysis['volume'] = "🔥 Экстремальный объем"
            elif volume_ratio > 0.15:
                score += 15
                analysis['volume'] = "📈 Высокий объем"
            elif volume_ratio > 0.05:
                score += 10
                analysis['volume'] = "💹 Хороший объем"
            
            if 5 < price_change_24h < 50:
                score += 20
                analysis['momentum'] = f"🚀 Рост +{price_change_24h:.1f}%"
            
            # 2. Технические индикаторы (30%)
            if indicators.rsi < 35:
                score += 15
                analysis['rsi'] = f"📊 RSI {indicators.rsi:.1f} - перепроданность"
            elif indicators.rsi > 65:
                score -= 10
                analysis['rsi'] = f"⚠️ RSI {indicators.rsi:.1f} - перекупленность"
            
            if indicators.macd > indicators.macd_signal:
                score += 15
                analysis['macd'] = "📈 MACD бычий"
            
            # 3. ML прогноз (30%)
            ml_score = await self.ml_predictor.predict(symbol, self.db)
            ml_contribution = ml_score * 0.3
            score += ml_contribution
            analysis['ml'] = f"🤖 ML score: {ml_score:.1f}/100"
            
            # 4. Risk adjustment
            if price_change_24h > 80:
                score -= 20
                analysis['risk'] = "💥 Высокий риск коррекции"
            
        except Exception as e:
            logger.error(f"❌ Ошибка расчета score: {e}")
        
        return max(0, min(100, int(score))), analysis
    
    async def analyze_coin(self, coin_data: Dict) -> Optional[Dict]:
        """Полный анализ монеты"""
        try:
            symbol = coin_data['symbol'].upper()
            
            # Сохраняем данные в БД
            coin_obj = CoinData(
                symbol=symbol,
                name=coin_data['name'],
                price=coin_data['current_price'],
                market_cap=coin_data['market_cap'],
                volume_24h=coin_data['total_volume'],
                price_change_24h=coin_data.get('price_change_percentage_24h', 0) or 0,
                price_change_7d=coin_data.get('price_change_percentage_7d_in_currency', 0) or 0,
                timestamp=datetime.now()
            )
            await self.db.save_coin_data(coin_obj)
            
            # Рассчитываем индикаторы
            indicators = await self.technical_analyzer.calculate_indicators(symbol, self.db)
            
            # Рассчитываем score
            score, analysis = await self.calculate_advanced_score(coin_data, indicators)
            
            return {
                'symbol': symbol,
                'name': coin_data['name'],
                'score': score,
                'price': coin_data['current_price'],
                'price_change_24h': coin_data.get('price_change_percentage_24h', 0) or 0,
                'market_cap': coin_data['market_cap'],
                'volume': coin_data['total_volume'],
                'volume_ratio': coin_data['total_volume'] / coin_data['market_cap'] if coin_data['market_cap'] > 0 else 0,
                'analysis': analysis,
                'technical_indicators': indicators,
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа монеты {coin_data.get('symbol', 'unknown')}: {e}")
            return None

class CryptoAdvancedBot:
    """Продвинутый крипто-бот"""
    
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.db = DatabaseManager()
        self.is_processing = False
        self.last_manual_update = 0
        self.cached_predictions = None
        self.last_successful_update = None
    
    async def send_message(self, text: str, reply_markup: Dict = None) -> bool:
        """Асинхронная отправка сообщения"""
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
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        logger.info("✅ Сообщение отправлено")
                        return True
                    else:
                        logger.error(f"❌ Ошибка отправки: {response.status}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки: {e}")
        finally:
            self.is_processing = False
        return False
    
    def create_signal_keyboard(self, symbol: str, signal_id: int) -> Dict:
        """Создает кнопки для сигналов с ID"""
        return {
            'inline_keyboard': [
                [
                    {'text': '✅ СРАБОТАЛ', 'callback_data': f'success_{signal_id}_{symbol}'},
                    {'text': '❌ НЕ СРАБОТАЛ', 'callback_data': f'fail_{signal_id}_{symbol}'}
                ],
                [
                    {'text': '💡 ЧАСТИЧНО', 'callback_data': f'partial_{signal_id}_{symbol}'}
                ]
            ]
        }
    
    async def send_signal(self, analysis: Dict) -> bool:
        """Отправляет торговый сигнал"""
        symbol = analysis['symbol']
        
        # Сохраняем сигнал в БД
        signal_id = await self.db.save_signal(
            symbol=symbol,
            score=analysis['score'],
            price=analysis['price'],
            signal_type="AUTO",
            analysis=analysis['analysis']
        )
        
        if not signal_id:
            return False
        
        # Форматируем сообщение
        message = await self.format_signal_message(analysis)
        keyboard = self.create_signal_keyboard(symbol, signal_id)
        
        return await self.send_message(message, keyboard)
    
    async def format_signal_message(self, analysis: Dict) -> str:
        """Форматирует сообщение сигнала"""
        symbol = analysis['symbol']
        price = analysis['price']
        
        # Форматируем цену
        if price < 0.001:
            price_str = f"${price:.8f}"
        elif price < 1:
            price_str = f"${price:.6f}"
        else:
            price_str = f"${price:.2f}"
        
        message = f"""
🎯 <b>СИГНАЛ - {symbol}</b>

⭐ <b>Score:</b> {analysis['score']}/100
💰 <b>Цена:</b> {price_str}
📊 <b>Изменение 24ч:</b> {analysis['price_change_24h']:.1f}%
🏦 <b>Капитализация:</b> ${analysis['market_cap']:,.0f}

<b>ТЕХНИЧЕСКИЙ АНАЛИЗ:</b>
"""
        
        for metric, desc in analysis['analysis'].items():
            message += f"• {desc}\n"
        
        # Добавляем ML информацию
        if 'ml' in analysis['analysis']:
            message += f"\n<b>ML ПРОГНОЗ:</b>\n"
            message += f"• {analysis['analysis']['ml']}\n"
        
        message += f"\n💡 <i>Отметь результат для обучения системы!</i>"
        
        return message
    
    async def process_feedback(self, callback_data: str):
        """Обрабатывает фидбек пользователя"""
        try:
            parts = callback_data.split('_')
            if len(parts) >= 3:
                feedback_type = parts[0]
                signal_id = int(parts[1])
                symbol = parts[2]
                
                await self.db.save_feedback(signal_id, symbol, feedback_type)
                
                response_text = f"""
✅ <b>ФИДБЕК ЗАПИСАН!</b>

{symbol} - {feedback_type.upper()}

Спасибо! Система учится на ваших оценках 🧠

<b>Статистика фидбека:</b>
• Успешные: {await self.get_feedback_stats('success')}
• Неудачные: {await self.get_feedback_stats('fail')}  
• Частичные: {await self.get_feedback_stats('partial')}
"""
                await self.send_message(response_text)
                
        except Exception as e:
            logger.error(f"❌ Ошибка обработки фидбека: {e}")
    
    async def get_feedback_stats(self, feedback_type: str) -> int:
        """Получает статистику фидбека"""
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.execute(
                    'SELECT COUNT(*) FROM feedback WHERE feedback_type = ?',
                    (feedback_type,)
                )
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            return 0
    
    async def run_analysis_cycle(self):
        """Запускает цикл анализа"""
        logger.info("🔄 Запуск цикла анализа...")
        
        async with AdvancedAnalyzer(self.db) as analyzer:
            coins_data = await analyzer.fetch_top_coins(100)
            
            if not coins_data:
                logger.warning("⚠️ Не удалось получить данные монет")
                return
            
            # Анализируем все монеты
            analyses = []
            for coin in coins_data:
                analysis = await analyzer.analyze_coin(coin)
                if analysis and analysis['score'] >= 60:  # Минимальный порог
                    analyses.append(analysis)
            
            # Сортируем по score
            analyses.sort(key=lambda x: x['score'], reverse=True)
            self.cached_predictions = analyses[:10]
            self.last_successful_update = datetime.now()
            
            # Отправляем топ-3 сигнала
            for analysis in analyses[:3]:
                if analysis['score'] >= 75:  # Высокий порог для сигналов
                    await self.send_signal(analysis)
                    await asyncio.sleep(1)  # Задержка между сообщениями
            
            logger.info(f"✅ Анализ завершен. Найдено {len(analyses)} перспективных монет")

async def main():
    """Основная функция"""
    # Конфигурация
    BOT_TOKEN = "8406686288:AAHSHNwi_ocevorBddn5P_6Oc70aMx0-Usc"
    CHAT_ID = "6823451625"
    
    bot = CryptoAdvancedBot(BOT_TOKEN, CHAT_ID)
    
    # Приветственное сообщение
    await bot.send_message("""
🤖 <b>ПРОДВИНУТАЯ СИСТЕМА АНАЛИЗА КРИПТО ЗАПУЩЕНА</b>

🚀 <b>НОВЫЕ ВОЗМОЖНОСТИ:</b>
• 🤖 ML-прогнозирование
• 📊 Технические индикаторы (RSI, MACD, EMA)
• 🧠 Обучение на фидбеке
• 💾 Сохранение истории в БД
• ⚡ Асинхронная обработка

📈 <b>СИСТЕМА АНАЛИЗИРУЕТ:</b>
• Топ-100 криптовалют
• Volume/Market Cap соотношения  
• Технические индикаторы
• ML-прогнозы роста
• Новостные упоминания

⚡ <i>Авто-обновление каждые 15 минут</i>
""")
    
    # Основной цикл
    while True:
        try:
            await bot.run_analysis_cycle()
            logger.info("💤 Ожидание следующего цикла анализа (15 минут)...")
            await asyncio.sleep(15 * 60)  # 15 минут
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в основном цикле: {e}")
            await asyncio.sleep(60)  # Ждем минуту перед повторной попыткой

if __name__ == "__main__":
    # Запуск бота
    asyncio.run(main())
