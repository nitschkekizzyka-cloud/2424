# crypto_advanced_bot.py (обновленная версия)

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
    
    async def show_top_predictions(self, force_update: bool = False):
        """Показывает топ-10 перспективных монет из полного анализа"""
        logger.info("🏆 Формирование топ-10 перспективных монет...")
        
        # Если есть кеш и не принудительное обновление - используем кеш
        if self.cached_predictions and not force_update:
            message = await self.format_top_predictions(
                self.cached_predictions[:10], 
                show_cache_info=True,
                update_time=self.last_successful_update
            )
            await self.send_message(message)
            return
        
        # Запускаем полный анализ
        async with AdvancedAnalyzer(self.db) as analyzer:
            try:
                # Параллельно загружаем топ-монеты и перспективные монеты
                top_coins_task = asyncio.create_task(analyzer.fetch_top_coins(50))
                potential_coins_task = asyncio.create_task(analyzer.fetch_potential_coins(150))
                
                top_coins, potential_coins = await asyncio.gather(
                    top_coins_task, potential_coins_task
                )
                
                # Объединяем и убираем дубликаты
                all_coins = top_coins + potential_coins
                unique_coins = {}
                for coin in all_coins:
                    symbol = coin['symbol'].upper()
                    if symbol not in unique_coins:
                        unique_coins[symbol] = coin
                
                coins_to_analyze = list(unique_coins.values())
                logger.info(f"📊 Всего монет для анализа: {len(coins_to_analyze)}")
                
                # Анализируем все монеты с ограничением параллелизма
                analyses = []
                semaphore = asyncio.Semaphore(10)
                
                async def analyze_with_semaphore(coin):
                    async with semaphore:
                        return await analyzer.analyze_coin(coin)
                
                analysis_tasks = [analyze_with_semaphore(coin) for coin in coins_to_analyze]
                results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
                
                # Собираем успешные анализы
                for result in results:
                    if isinstance(result, dict) and result.get('score', 0) >= 40:  # Минимальный порог для топа
                        analyses.append(result)
                
                # Сортируем по score и берем топ-10
                analyses.sort(key=lambda x: x['score'], reverse=True)
                top_10 = analyses[:10]
                self.cached_predictions = analyses  # Сохраняем все анализы для кеша
                self.last_successful_update = datetime.now()
                
                # Форматируем и отправляем топ-10
                message = await self.format_top_predictions(top_10, force_update=force_update)
                await self.send_message(message)
                
                logger.info(f"✅ Топ-10 сформирован. Лучшая монета: {top_10[0]['symbol']} - {top_10[0]['score']}%")
                
            except Exception as e:
                logger.error(f"❌ Ошибка формирования топа: {e}")
                await self.send_message("❌ Не удалось получить данные для топа. Попробуйте позже.")
    
    async def format_top_predictions(self, predictions: List[Dict], 
                                   show_cache_info: bool = False, 
                                   update_time: datetime = None,
                                   force_update: bool = False) -> str:
        """Форматирует топ-10 перспективных монет"""
        if not predictions:
            return "📊 <b>ТОП 10 ПЕРСПЕКТИВНЫХ МОНЕТ</b>\n\nНа данный момент нет подходящих монет для анализа."
        
        message = "🏆 <b>ТОП 10 ПЕРСПЕКТИВНЫХ МОНЕТ</b>\n\n"
        
        for i, coin in enumerate(predictions, 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            
            # Определяем тип монеты для эмодзи
            type_emoji = "🆕" if coin.get('is_new') else "📈" if coin.get('discovery_source') == DiscoverySource.VOLUME_SCREENER.value else "🏆"
            
            message += f"{emoji} {type_emoji} <b>{coin['symbol']}</b> - Score: {coin['score']}%\n"
            message += f"   💰 {self.format_price(coin['price'])} | 📈 {coin['price_change_24h']:.1f}% | 🚀 {coin['price_change_7d']:.1f}%\n"
            
            # Показываем основной фактор успеха
            if coin['analysis']:
                main_reason = list(coin['analysis'].values())[0]
                # Обрезаем длинные описания
                if len(main_reason) > 50:
                    main_reason = main_reason[:47] + "..."
                message += f"   🔍 {main_reason}\n"
            
            # Показываем бонус если есть
            if coin.get('bonus_applied', 0) > 0:
                message += f"   💎 Бонус: +{coin['bonus_applied']}%\n"
            
            message += "\n"
        
        # Информация об обновлении
        if force_update:
            message += "⚡ <b>Данные обновлены только что</b>\n"
        elif show_cache_info and update_time:
            time_diff = datetime.now() - update_time
            minutes_ago = int(time_diff.total_seconds() / 60)
            message += f"💾 <i>Данные актуальны на {update_time.strftime('%H:%M:%S')} ({minutes_ago} мин. назад)</i>\n"
        
        message += "🔄 <i>Авто-обновление каждые 15 минут</i>"
        
        return message
    
    async def run_analysis_cycle(self):
        """Запускает улучшенный цикл анализа с формированием топа"""
        logger.info("🔄 Запуск цикла анализа с формированием топа...")
        
        async with AdvancedAnalyzer(self.db) as analyzer:
            try:
                # Параллельно загружаем топ-монеты и перспективные монеты
                top_coins_task = asyncio.create_task(analyzer.fetch_top_coins(50))
                potential_coins_task = asyncio.create_task(analyzer.fetch_potential_coins(150))
                
                top_coins, potential_coins = await asyncio.gather(
                    top_coins_task, potential_coins_task
                )
                
                # Объединяем и убираем дубликаты
                all_coins = top_coins + potential_coins
                unique_coins = {}
                for coin in all_coins:
                    symbol = coin['symbol'].upper()
                    if symbol not in unique_coins:
                        unique_coins[symbol] = coin
                
                coins_to_analyze = list(unique_coins.values())
                logger.info(f"📊 Всего монет для анализа: {len(coins_to_analyze)}")
                
                # Анализируем все монеты с ограничением параллелизма
                analyses = []
                semaphore = asyncio.Semaphore(10)
                
                async def analyze_with_semaphore(coin):
                    async with semaphore:
                        return await analyzer.analyze_coin(coin)
                
                analysis_tasks = [analyze_with_semaphore(coin) for coin in coins_to_analyze]
                results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
                
                # Собираем успешные анализы
                for result in results:
                    if isinstance(result, dict) and result.get('score', 0) >= 40:
                        analyses.append(result)
                
                # Сортируем по score и сохраняем
                analyses.sort(key=lambda x: x['score'], reverse=True)
                self.cached_predictions = analyses
                self.last_successful_update = datetime.now()
                
                # Автоматически отправляем топ-5 при каждом цикле
                top_5 = analyses[:5]
                for analysis in top_5:
                    if analysis['score'] >= 75:  # Высокий порог для авто-сигналов
                        if await self.send_signal(analysis):
                            logger.info(f"✅ Авто-сигнал отправлен: {analysis['symbol']} - {analysis['score']}%")
                            await asyncio.sleep(2)
                
                # Переобучаем ML модель раз в сутки
                if (datetime.now() - self.last_stats_update).total_seconds() > 24 * 3600:
                    await analyzer.ml_model.retrain_model()
                    self.last_stats_update = datetime.now()
                
                logger.info(f"✅ Анализ завершен. Топ-1: {analyses[0]['symbol']} - {analyses[0]['score']}%")
                
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле анализа: {e}")

    async def handle_manual_update(self):
        """Обрабатывает ручное обновление топа"""
        current_time = time.time()
        
        # Проверяем таймер (30 секунд между обновлениями)
        if hasattr(self, 'last_manual_update'):
            time_since_last = current_time - self.last_manual_update
            if time_since_last < 30:
                seconds_left = 30 - int(time_since_last)
                return f"⏰ Обновить можно через {seconds_left} сек."
        
        self.last_manual_update = current_time
        await self.show_top_predictions(force_update=True)
        return "✅ Топ-10 обновлен!"

    async def send_detailed_analysis(self, symbol: str):
        """Показывает детальный анализ конкретной монеты"""
        async with AdvancedAnalyzer(self.db) as analyzer:
            # Ищем монету в кеше
            if self.cached_predictions:
                for coin in self.cached_predictions:
                    if coin['symbol'].upper() == symbol.upper():
                        message = await self.format_detailed_analysis(coin)
                        await self.send_message(message)
                        return
            
            # Если не найдено в кеше, делаем отдельный анализ
            logger.info(f"🔍 Детальный анализ монеты: {symbol}")
            # Здесь можно добавить поиск монеты через CoinGecko API
            await self.send_message(f"🔍 Монета {symbol} не найдена в текущем анализе. Попробуйте обновить топ.")

    async def format_detailed_analysis(self, analysis: Dict) -> str:
        """Форматирует детальный анализ монеты"""
        symbol = analysis['symbol']
        
        message = f"""
🔍 <b>ДЕТАЛЬНЫЙ АНАЛИЗ - {symbol}</b>

⭐ <b>Общий счет:</b> {analysis['score']}/100
{'💎 <b>Бонус:</b> +' + str(analysis['bonus_applied']) + '%' if analysis.get('bonus_applied', 0) > 0 else ''}
💰 <b>Цена:</b> {self.format_price(analysis['price'])}
📊 <b>Изменение 24ч:</b> {analysis['price_change_24h']:.1f}%
🚀 <b>Изменение 7д:</b> {analysis['price_change_7d']:.1f}%
🏦 <b>Капитализация:</b> ${analysis['market_cap']:,.0f}
💧 <b>Объем/Капитализация:</b> {analysis['volume_ratio']:.2%}
🎯 <b>Тип:</b> {'🆕 Новая монета' if analysis.get('is_new') else '📈 Восходящая звезда' if analysis.get('discovery_source') == DiscoverySource.VOLUME_SCREENER.value else '🏆 Топ монета'}

<b>ПОДРОБНЫЙ АНАЛИЗ:</b>
"""
        
        for metric, desc in analysis['analysis'].items():
            message += f"• {desc}\n"
        
        # Добавляем технические индикаторы если есть
        if analysis.get('technical_indicators'):
            indicators = analysis['technical_indicators']
            message += f"\n<b>ТЕХНИЧЕСКИЕ ИНДИКАТОРЫ:</b>\n"
            message += f"• RSI: {indicators.get('rsi', 0):.1f}\n"
            message += f"• MACD: {indicators.get('macd', 0):.4f}\n"
            message += f"• SMA 20: {self.format_price(indicators.get('sma_20', 0))}\n"
        
        # Рекомендация на основе score
        if analysis['score'] >= 80:
            recommendation = "🚀 <b>СИЛЬНЫЙ СИГНАЛ</b> - Высокий потенциал роста"
        elif analysis['score'] >= 65:
            recommendation = "📈 <b>ХОРОШИЙ СИГНАЛ</b> - Умеренный потенциал"
        elif analysis['score'] >= 50:
            recommendation = "💡 <b>СРЕДНИЙ СИГНАЛ</b> - Требует осторожности"
        else:
            recommendation = "⚠️ <b>СЛАБЫЙ СИГНАЛ</b> - Высокий риск"
        
        message += f"\n<b>РЕКОМЕНДАЦИЯ:</b>\n{recommendation}"
        
        return message

# Добавляем обработчики команд в основной цикл
async def handle_message(self, text: str):
    """Обрабатывает текстовые сообщения"""
    if text == '🏆 ТОП 10':
        await self.show_top_predictions()
    elif text == '🔄 ОБНОВИТЬ':
        result = await self.handle_manual_update()
        if isinstance(result, str):
            await self.send_message(result)
    elif text == '📊 СТАТИСТИКА':
        await self.show_statistics()
    elif text == '🔍 АНАЛИЗ МОНЕТЫ':
        await self.ask_for_coin_symbol()
    elif text.startswith('/analyze '):
        symbol = text.replace('/analyze ', '').strip().upper()
        await self.send_detailed_analysis(symbol)
    else:
        # Предполагаем что это символ монеты
        if 2 <= len(text) <= 10 and text.replace(' ', '').isalnum():
            await self.send_detailed_analysis(text)
        else:
            await self.send_message("❌ Неизвестная команда. Используйте меню.")

# Обновляем приветственное сообщение
WELCOME_MESSAGE = """
🤖 <b>ПРОДВИНУТАЯ СИСТЕМА АНАЛИЗА КРИПТО</b>

🚀 <b>ОСНОВНЫЕ ВОЗМОЖНОСТИ:</b>

🏆 <b>ТОП 10 ПЕРСПЕКТИВНЫХ МОНЕТ</b>
- Автоматический анализ 200+ монет
- Рейтинг на основе сложного алгоритма
- Включает новые и восходящие монеты

🔍 <b>ДЕТАЛЬНЫЙ АНАЛИЗ</b>
- Введите символ монеты для глубокого анализа
- Технические индикаторы и метрики
- Персональные рекомендации

📊 <b>АВТО-СИГНАЛЫ</b>
- Автоматические уведомления о сильных сигналах
- Обучение на ваших оценках
- Статистика эффективности

⚡ <b>Используйте кнопки ниже для навигации!</b>
"""
