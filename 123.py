# crypto_advanced_bot.py
import asyncio
import aiohttp
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set, Any
import logging
from dataclasses import dataclass, asdict
import json
import time
import os
from enum import Enum
import statistics

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crypto_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DiscoverySource(Enum):
    TOP_MARKET_CAP = "top_market_cap"
    VOLUME_SCREENER = "volume_screener"
    NEW_COINS_SEARCH = "new_coins_search"

class SignalStatus(Enum):
    ACTIVE = "active"
    SUCCESS = "success"
    FAIL = "fail"
    PARTIAL = "partial"

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
    is_new: bool = False
    discovery_source: str = DiscoverySource.TOP_MARKET_CAP.value

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

@dataclass
class SignalData:
    """Данные сигнала"""
    symbol: str
    score: int
    price: float
    signal_type: str
    analysis: Dict[str, str]
    timestamp: datetime
    discovery_source: str
    is_new: bool = False
    bonus_applied: int = 0
    status: str = SignalStatus.ACTIVE.value

class DatabaseManager:
    """Менеджер базы данных для хранения истории"""
    
    def __init__(self, db_path: str = "crypto_bot_advanced.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Инициализация таблиц БД"""
        with sqlite3.connect(self.db_path) as conn:
            # Таблица исторических данных монет
            conn.execute('''
                CREATE TABLE IF NOT EXISTS coin_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    name TEXT NOT NULL,
                    price REAL NOT NULL,
                    market_cap REAL NOT NULL,
                    volume_24h REAL NOT NULL,
                    price_change_24h REAL NOT NULL,
                    price_change_7d REAL NOT NULL,
                    is_new BOOLEAN DEFAULT FALSE,
                    discovery_source TEXT NOT NULL,
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
                    discovery_source TEXT NOT NULL,
                    is_new BOOLEAN DEFAULT FALSE,
                    bonus_applied INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active',
                    timestamp DATETIME NOT NULL,
                    feedback_timestamp DATETIME
                )
            ''')
            
            # Таблица фидбека
            conn.execute('''
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    feedback_type TEXT NOT NULL,
                    user_comment TEXT,
                    original_score INTEGER NOT NULL,
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
            
            # Таблица статистики моделей
            conn.execute('''
                CREATE TABLE IF NOT EXISTS model_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_type TEXT NOT NULL,
                    parameters TEXT NOT NULL,
                    accuracy REAL,
                    total_signals INTEGER,
                    successful_signals INTEGER,
                    timestamp DATETIME NOT NULL
                )
            ''')
            
            conn.commit()
    
    async def save_coin_data(self, coin_data: CoinData):
        """Сохраняет данные монеты в БД"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO coin_history 
                    (symbol, name, price, market_cap, volume_24h, price_change_24h, 
                     price_change_7d, is_new, discovery_source, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    coin_data.symbol, coin_data.name, coin_data.price, coin_data.market_cap,
                    coin_data.volume_24h, coin_data.price_change_24h, coin_data.price_change_7d,
                    coin_data.is_new, coin_data.discovery_source, coin_data.timestamp
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения данных монеты: {e}")
    
    async def save_signal(self, signal_data: SignalData) -> int:
        """Сохраняет сигнал в БД и возвращает ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    INSERT INTO signals 
                    (symbol, score, price, signal_type, analysis, discovery_source, 
                     is_new, bonus_applied, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    signal_data.symbol, signal_data.score, signal_data.price,
                    signal_data.signal_type, json.dumps(signal_data.analysis),
                    signal_data.discovery_source, signal_data.is_new,
                    signal_data.bonus_applied, signal_data.timestamp
                ))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения сигнала: {e}")
            return -1
    
    async def save_feedback(self, signal_id: int, symbol: str, feedback_type: str, 
                          original_score: int, comment: str = ""):
        """Сохраняет фидбек пользователя и обновляет статус сигнала"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Сохраняем фидбек
                conn.execute('''
                    INSERT INTO feedback 
                    (signal_id, symbol, feedback_type, user_comment, original_score, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (signal_id, symbol, feedback_type, comment, original_score, datetime.now()))
                
                # Обновляем статус сигнала
                conn.execute('''
                    UPDATE signals SET status = ?, feedback_timestamp = ? 
                    WHERE id = ?
                ''', (feedback_type, datetime.now(), signal_id))
                
                conn.commit()
                logger.info(f"✅ Фидбек сохранен: {symbol} - {feedback_type}")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения фидбека: {e}")
    
    async def get_signal_stats(self, days: int = 90) -> Dict[str, Any]:
        """Получает статистику сигналов за указанный период"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                since_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
                
                # Общая статистика
                cursor = conn.execute('''
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
                        SUM(CASE WHEN status = 'fail' THEN 1 ELSE 0 END) as fail,
                        SUM(CASE WHEN status = 'partial' THEN 1 ELSE 0 END) as partial,
                        AVG(score) as avg_score
                    FROM signals 
                    WHERE timestamp >= ? AND status != 'active'
                ''', (since_date,))
                
                stats = cursor.fetchone()
                
                # Статистика по источникам
                source_cursor = conn.execute('''
                    SELECT 
                        discovery_source,
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success
                    FROM signals 
                    WHERE timestamp >= ? AND status != 'active'
                    GROUP BY discovery_source
                ''', (since_date,))
                
                source_stats = {}
                for row in source_cursor:
                    source_stats[row[0]] = {
                        'total': row[1],
                        'success': row[2],
                        'success_rate': (row[2] / row[1]) * 100 if row[1] > 0 else 0
                    }
                
                # Статистика по новым монетам
                new_coins_cursor = conn.execute('''
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success
                    FROM signals 
                    WHERE timestamp >= ? AND is_new = TRUE AND status != 'active'
                ''', (since_date,))
                
                new_coins_stats = new_coins_cursor.fetchone()
                
                return {
                    'total_signals': stats[0],
                    'successful_signals': stats[1],
                    'failed_signals': stats[2],
                    'partial_signals': stats[3],
                    'success_rate': (stats[1] / stats[0]) * 100 if stats[0] > 0 else 0,
                    'average_score': stats[4],
                    'source_stats': source_stats,
                    'new_coins_stats': {
                        'total': new_coins_stats[0],
                        'success': new_coins_stats[1],
                        'success_rate': (new_coins_stats[1] / new_coins_stats[0]) * 100 if new_coins_stats[0] > 0 else 0
                    }
                }
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            return {}
    
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
            logger.error(f"❌ Ошибка получения исторических данных: {e}")
            return pd.DataFrame()

class PotentialCoinsCache:
    """Кэш для перспективных монет"""
    
    def __init__(self, cache_file: str = "potential_coins_cache.json"):
        self.cache_file = cache_file
        self.cache_duration = 6 * 3600  # 6 часов
    
    def load_cache(self) -> Optional[List[Dict]]:
        """Загружает кэш из файла"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    # Проверяем актуальность кэша
                    cache_time = datetime.fromisoformat(cache_data['timestamp'])
                    if (datetime.now() - cache_time).total_seconds() < self.cache_duration:
                        logger.info(f"✅ Используем кэшированные данные: {len(cache_data['coins'])} монет")
                        return cache_data['coins']
                    else:
                        logger.info("⚠️ Кэш устарел, требуется обновление")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки кэша: {e}")
        return None
    
    def save_cache(self, coins: List[Dict]):
        """Сохраняет кэш в файл"""
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'coins': coins
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ Кэш сохранен: {len(coins)} монет")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения кэша: {e}")

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
        macd_values = []
        for i in range(len(prices)):
            if i >= 25:
                price_window = prices[i-25:i+1]
                ema_12_val = TechnicalAnalyzer.calculate_ema(price_window, 12)
                ema_26_val = TechnicalAnalyzer.calculate_ema(price_window, 26)
                macd_values.append(ema_12_val - ema_26_val)
        
        if len(macd_values) >= 9:
            signal = TechnicalAnalyzer.calculate_ema(macd_values, 9)
        else:
            signal = macd_values[-1] if macd_values else macd
        
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

class MLModel:
    """Простая ML модель для пересчета весов на основе фидбека"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.weights = {
            'volume_ratio': 0.3,
            'price_momentum': 0.25,
            'market_cap': 0.2,
            'technical_indicators': 0.15,
            'new_coin_bonus': 0.1
        }
    
    async def retrain_model(self):
        """Переобучает модель на основе исторических данных"""
        try:
            stats = await self.db.get_signal_stats(90)
            
            if stats.get('total_signals', 0) < 10:
                logger.info("⚠️ Недостаточно данных для переобучения модели")
                return
            
            # Анализируем успешность различных факторов
            success_rate = stats['success_rate']
            new_coins_success = stats['new_coins_stats']['success_rate']
            
            # Корректируем веса на основе успешности
            if new_coins_success > success_rate + 10:
                # Новые монеты показывают лучшие результаты - увеличиваем бонус
                self.weights['new_coin_bonus'] = min(0.2, self.weights['new_coin_bonus'] + 0.02)
            elif new_coins_success < success_rate - 10:
                # Новые монеты показывают худшие результаты - уменьшаем бонус
                self.weights['new_coin_bonus'] = max(0.05, self.weights['new_coin_bonus'] - 0.02)
            
            # Анализ успешности по источникам
            source_stats = stats.get('source_stats', {})
            for source, data in source_stats.items():
                if data['success_rate'] > success_rate + 15:
                    logger.info(f"🎯 Источник {source} показывает отличные результаты: {data['success_rate']:.1f}%")
            
            logger.info(f"🔄 Модель переобучена. Новые веса: {self.weights}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка переобучения модели: {e}")
    
    def get_weights(self) -> Dict[str, float]:
        """Возвращает текущие веса модели"""
        return self.weights.copy()

class AdvancedAnalyzer:
    """Продвинутый анализатор с поиском перспективных монет"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.technical_analyzer = TechnicalAnalyzer()
        self.ml_model = MLModel(db)
        self.session = None
        self.cache_manager = PotentialCoinsCache()
        self.exclude_coins = {'usdt', 'usdc', 'busd', 'dai', 'tusd', 'ust', 'fdusd', 'pyusd'}
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_top_coins(self, limit: int = 50) -> List[Dict]:
        """Загружает топ монет по рыночной капитализации"""
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
                        {**coin, 'discovery_source': DiscoverySource.TOP_MARKET_CAP.value}
                        for coin in coins 
                        if coin['symbol'] not in self.exclude_coins
                    ]
                    logger.info(f"✅ Загружено топ {len(filtered_coins)} монет")
                    return filtered_coins
                else:
                    logger.error(f"❌ Ошибка API при загрузке топ монет: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки топ монет: {e}")
            return []
    
    async def fetch_potential_coins(self, limit: int = 150) -> List[Dict]:
        """Ищет перспективные новые и низкорейтинговые монеты"""
        
        # Пробуем загрузить из кэша
        cached_coins = self.cache_manager.load_cache()
        if cached_coins is not None:
            return cached_coins
        
        logger.info("🔄 Поиск перспективных монет...")
        potential_coins = []
        
        try:
            # Стратегия: Поиск по рынкам с фильтрацией
            url = "https://api.coingecko.com/api/v3/coins/markets"
            
            for page in range(1, 5):  # Проверяем первые 4 страницы (200 монет)
                params = {
                    "vs_currency": "usd",
                    "order": "volume_desc",  # Сортировка по объему
                    "per_page": 50,
                    "page": page,
                    "sparkline": "false",
                    "price_change_percentage": "7d,30d"
                }
                
                async with self.session.get(url, params=params, timeout=30) as response:
                    if response.status == 200:
                        coins = await response.json()
                        
                        for coin in coins:
                            if self._is_potential_coin(coin):
                                coin_data = {
                                    **coin,
                                    'discovery_source': DiscoverySource.VOLUME_SCREENER.value,
                                    'is_new': self._check_if_new_coin(coin)
                                }
                                potential_coins.append(coin_data)
                    
                    await asyncio.sleep(1)  # Rate limiting
            
            # Ограничиваем количество и сохраняем в кэш
            potential_coins = potential_coins[:limit]
            self.cache_manager.save_cache(potential_coins)
            
            logger.info(f"✅ Найдено {len(potential_coins)} перспективных монет")
            return potential_coins
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска перспективных монет: {e}")
            return []
    
    def _is_potential_coin(self, coin: Dict) -> bool:
        """Проверяет, соответствует ли монета критериям перспективности"""
        try:
            # Базовые проверки
            if coin['symbol'] in self.exclude_coins:
                return False
            
            if not coin.get('market_cap') or coin['market_cap'] is None:
                return False
            
            if not coin.get('total_volume') or coin['total_volume'] is None:
                return False
            
            # Основные критерии
            market_cap = coin['market_cap']
            volume_24h = coin['total_volume']
            price_change_7d = coin.get('price_change_percentage_7d_in_currency', 0) or 0
            
            # Критерии отбора
            criteria = [
                market_cap < 50000000,           # Капитализация < $50M
                volume_24h > 100000,            # Объем > $100K
                price_change_7d > 30,           # Рост за 7 дней > 30%
                volume_24h / max(market_cap, 1) > 0.05,  # Volume/MCAP ratio > 5%
            ]
            
            return all(criteria)
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки монеты {coin.get('symbol', 'unknown')}: {e}")
            return False
    
    def _check_if_new_coin(self, coin: Dict) -> bool:
        """Проверяет, является ли монета новой (< 90 дней)"""
        # Эвристика: новые монеты часто имеют высокий volume/mcap ratio
        # и относительно низкую капитализацию
        market_cap = coin.get('market_cap', 0)
        volume_ratio = coin['total_volume'] / max(market_cap, 1)
        
        return volume_ratio > 0.3 and market_cap < 20000000
    
    async def calculate_advanced_score(self, coin: Dict, indicators: TechnicalIndicators) -> Tuple[int, Dict]:
        """Расширенный расчет score с ML весами"""
        score = 0
        analysis = {}
        weights = self.ml_model.get_weights()
        
        try:
            symbol = coin['symbol'].upper()
            
            # 1. Volume Ratio (30%)
            volume_ratio = coin['total_volume'] / coin['market_cap'] if coin['market_cap'] > 0 else 0
            volume_score = 0
            
            if volume_ratio > 0.3:
                volume_score = 30
                analysis['volume'] = "🔥 Экстремальный объем"
            elif volume_ratio > 0.15:
                volume_score = 20
                analysis['volume'] = "📈 Высокий объем"
            elif volume_ratio > 0.05:
                volume_score = 10
                analysis['volume'] = "💹 Хороший объем"
            
            score += volume_score * weights['volume_ratio']
            
            # 2. Price Momentum (25%)
            price_change_24h = coin.get('price_change_percentage_24h', 0) or 0
            price_change_7d = coin.get('price_change_percentage_7d_in_currency', 0) or 0
            momentum_score = 0
            
            if 10 < price_change_24h < 50 and price_change_7d > 20:
                momentum_score = 25
                analysis['momentum'] = f"🚀 Сильный рост +{price_change_24h:.1f}% (7д: +{price_change_7d:.1f}%)"
            elif 5 < price_change_24h < 10 and price_change_7d > 10:
                momentum_score = 15
                analysis['momentum'] = f"📈 Умеренный рост +{price_change_24h:.1f}%"
            
            score += momentum_score * weights['price_momentum']
            
            # 3. Market Cap (20%)
            market_cap = coin['market_cap']
            market_cap_score = 0
            
            if market_cap < 50000000:
                market_cap_score = 20
                analysis['market_cap'] = "🏦 Малая капа - высокий потенциал"
            elif market_cap < 200000000:
                market_cap_score = 10
                analysis['market_cap'] = "🏦 Средняя капа"
            
            score += market_cap_score * weights['market_cap']
            
            # 4. Technical Indicators (15%)
            technical_score = 0
            if indicators.rsi < 35:
                technical_score += 8
                analysis['rsi'] = f"📊 RSI {indicators.rsi:.1f} - перепроданность"
            elif indicators.rsi > 65:
                technical_score -= 5
                analysis['rsi'] = f"⚠️ RSI {indicators.rsi:.1f} - перекупленность"
            
            if indicators.macd > indicators.macd_signal:
                technical_score += 7
                analysis['macd'] = "📈 MACD бычий"
            
            score += technical_score * weights['technical_indicators']
            
            # 5. Risk Adjustment
            if price_change_24h > 80:
                score -= 15
                analysis['risk'] = "💥 Высокий риск коррекции"
            elif price_change_24h < -20:
                score += 5  # Возможность отскока
                analysis['risk'] = f"🔄 Просадка {price_change_24h:.1f}% - потенциал отскока"
                
        except Exception as e:
            logger.error(f"❌ Ошибка расчета score: {e}")
        
        base_score = max(0, min(100, int(score)))
        return base_score, analysis
    
    async def analyze_coin(self, coin_data: Dict) -> Optional[Dict]:
        """Полный анализ монеты с улучшенной логикой"""
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
                timestamp=datetime.now(),
                is_new=coin_data.get('is_new', False),
                discovery_source=coin_data.get('discovery_source', DiscoverySource.TOP_MARKET_CAP.value)
            )
            await self.db.save_coin_data(coin_obj)
            
            # Рассчитываем индикаторы
            indicators = await self.technical_analyzer.calculate_indicators(symbol, self.db)
            
            # Рассчитываем score
            base_score, analysis = await self.calculate_advanced_score(coin_data, indicators)
            
            # Применяем бонус для новых монет
            final_score = base_score
            bonus_applied = 0
            
            if coin_data.get('is_new', False):
                bonus = 15
                final_score = min(100, base_score + bonus)
                bonus_applied = bonus
                analysis['new_coin_bonus'] = f"🆕 НОВАЯ МОНЕТА - бонус +{bonus}%"
            
            return {
                'symbol': symbol,
                'name': coin_data['name'],
                'score': final_score,
                'base_score': base_score,
                'price': coin_data['current_price'],
                'price_change_24h': coin_data.get('price_change_percentage_24h', 0) or 0,
                'price_change_7d': coin_data.get('price_change_percentage_7d_in_currency', 0) or 0,
                'market_cap': coin_data['market_cap'],
                'volume': coin_data['total_volume'],
                'volume_ratio': coin_data['total_volume'] / coin_data['market_cap'] if coin_data['market_cap'] > 0 else 0,
                'analysis': analysis,
                'technical_indicators': asdict(indicators),
                'is_new': coin_data.get('is_new', False),
                'discovery_source': coin_data.get('discovery_source', DiscoverySource.TOP_MARKET_CAP.value),
                'bonus_applied': bonus_applied,
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа монеты {coin_data.get('symbol', 'unknown')}: {e}")
            return None

class CryptoAdvancedBot:
    """Продвинутый крипто-бот с автообучением"""
    
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.db = DatabaseManager()
        self.is_processing = False
        self.cached_predictions = None
        self.last_successful_update = None
        self.last_stats_update = datetime.now() - timedelta(hours=24)
    
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
    
    def format_price(self, price: float) -> str:
        """Форматирует цену в зависимости от величины"""
        if price is None:
            return "N/A"
        elif price < 0.001:
            return f"${price:.8f}"
        elif price < 1:
            return f"${price:.6f}"
        else:
            return f"${price:.2f}"
    
    async def format_signal_message(self, analysis: Dict) -> str:
        """Форматирует сообщение сигнала с информацией о типе монеты"""
        symbol = analysis['symbol']
        price = analysis['price']
        
        # Заголовок с типом монеты
        if analysis.get('is_new'):
            header = f"🎯 <b>СИГНАЛ - {symbol} 🆕 НОВАЯ МОНЕТА</b>"
        elif analysis.get('discovery_source') == DiscoverySource.VOLUME_SCREENER.value:
            header = f"🎯 <b>СИГНАЛ - {symbol} 📈 ВОСХОДЯЩАЯ ЗВЕЗДА</b>"
        else:
            header = f"🎯 <b>СИГНАЛ - {symbol}</b>"
        
        message = f"""
{header}

⭐ <b>Score:</b> {analysis['score']}/100
💰 <b>Цена:</b> {self.format_price(price)}
📊 <b>Изменение 24ч:</b> {analysis['price_change_24h']:.1f}%
🚀 <b>Изменение 7д:</b> {analysis['price_change_7d']:.1f}%
🏦 <b>Капитализация:</b> ${analysis['market_cap']:,.0f}
💧 <b>Объем/Капитализация:</b> {analysis['volume_ratio']:.2%}

<b>АНАЛИЗ:</b>
"""
        
        for metric, desc in analysis['analysis'].
