import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons/lucide_icons.dart';
import '../theme/app_theme.dart';
import '../widgets/source_badge.dart';
import '../widgets/stat_card.dart';
import '../widgets/feature_card.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      child: Column(
        children: [
          _HeroSection(),
          const SizedBox(height: 32),
          _FeaturesSection(),
          const SizedBox(height: 32),
          _SourcesSection(),
          const SizedBox(height: 48),
        ],
      ),
    );
  }
}

class _HeroSection extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final isWide = MediaQuery.of(context).size.width > 700;

    return Container(
      width: double.infinity,
      padding: EdgeInsets.symmetric(horizontal: 24, vertical: isWide ? 60 : 40),
      decoration: BoxDecoration(
        gradient: RadialGradient(
          center: const Alignment(-0.6, -0.3),
          radius: 1.5,
          colors: [AppColors.accent.withOpacity(0.06), Colors.transparent],
        ),
      ),
      child: Column(
        crossAxisAlignment: isWide ? CrossAxisAlignment.start : CrossAxisAlignment.center,
        children: [
          Text(
            'Тендеры, подрядчики\nи заказы — одна платформа',
            style: TextStyle(
              fontSize: isWide ? 38 : 28,
              fontWeight: FontWeight.w900,
              height: 1.1,
              letterSpacing: -1,
            ),
            textAlign: isWide ? TextAlign.left : TextAlign.center,
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: isWide ? 500 : double.infinity,
            child: Text(
              'Агрегатор тендеров со всех площадок. Справочник компаний из ЕГРЮЛ. '
              'Заявки на субподряд. Всё в одном окне.',
              style: TextStyle(fontSize: 15, color: AppColors.textSecondary, height: 1.6),
              textAlign: isWide ? TextAlign.left : TextAlign.center,
            ),
          ),
          const SizedBox(height: 24),
          // Search bar
          Container(
            constraints: const BoxConstraints(maxWidth: 560),
            child: TextField(
              decoration: InputDecoration(
                hintText: 'Поиск тендеров, компаний, ОКВЭД...',
                prefixIcon: const Icon(LucideIcons.search, size: 18, color: AppColors.textMuted),
                suffixIcon: Padding(
                  padding: const EdgeInsets.all(6),
                  child: ElevatedButton(
                    onPressed: () => context.go('/tenders'),
                    child: const Text('Найти'),
                  ),
                ),
              ),
              onSubmitted: (q) => context.go('/tenders?q=$q'),
            ),
          ),
          const SizedBox(height: 20),
          // Source badges
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: const [
              SourceBadge(name: 'ЕИС', color: AppColors.sourceEis),
              SourceBadge(name: 'РТС', color: AppColors.sourceRts),
              SourceBadge(name: 'Сбер-АСТ', color: AppColors.sourceSber),
              SourceBadge(name: 'Корпоративные', color: AppColors.sourceCorp),
              SourceBadge(name: 'Субподряды', color: AppColors.sourceSub),
            ],
          ),
          const SizedBox(height: 28),
          // Stats row
          Wrap(
            spacing: 32,
            runSpacing: 16,
            children: const [
              StatCard(value: '7', label: 'ПЛОЩАДОК'),
              StatCard(value: '48 320', label: 'ТЕНДЕРОВ'),
              StatCard(value: '4 812', label: 'КОМПАНИЙ'),
              StatCard(value: '85', label: 'РЕГИОНОВ'),
            ],
          ),
        ],
      ),
    );
  }
}

class _FeaturesSection extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: LayoutBuilder(builder: (context, constraints) {
        final cols = constraints.maxWidth > 900 ? 3 : constraints.maxWidth > 500 ? 2 : 1;
        return Wrap(
          spacing: 14,
          runSpacing: 14,
          children: [
            FeatureCard(
              icon: LucideIcons.fileText,
              title: 'Агрегатор тендеров',
              description: 'Закупки с 7 площадок: ЕИС, РТС, Сбербанк-АСТ, корпоративные, субподряды.',
              highlighted: true,
              onTap: () => context.go('/tenders'),
              width: (constraints.maxWidth - 14 * (cols - 1)) / cols,
            ),
            FeatureCard(
              icon: LucideIcons.building2,
              title: 'Справочник компаний',
              description: '4 800+ компаний из ЕГРЮЛ: реквизиты, финансы, СРО, тендерная история.',
              onTap: () => context.go('/companies'),
              width: (constraints.maxWidth - 14 * (cols - 1)) / cols,
            ),
            FeatureCard(
              icon: LucideIcons.clipboardList,
              title: 'Заявки на субподряд',
              description: 'Прямые заказы от генподрядчиков. Разместите заявку бесплатно.',
              highlighted: true,
              onTap: () => context.go('/requests'),
              width: (constraints.maxWidth - 14 * (cols - 1)) / cols,
            ),
            FeatureCard(
              icon: LucideIcons.map,
              title: 'Карта регионов',
              description: 'Компании и тендеры на карте РФ. Лицензионные участки.',
              onTap: () {},
              width: (constraints.maxWidth - 14 * (cols - 1)) / cols,
            ),
            FeatureCard(
              icon: LucideIcons.shoppingCart,
              title: 'Маркетплейс',
              description: 'Оборудование, спецтехника, материалы от поставщиков.',
              onTap: () {},
              width: (constraints.maxWidth - 14 * (cols - 1)) / cols,
            ),
            FeatureCard(
              icon: LucideIcons.search,
              title: 'Умный поиск',
              description: 'Мгновенный поиск по ОКВЭД, региону. Push-уведомления.',
              onTap: () => context.go('/tenders'),
              width: (constraints.maxWidth - 14 * (cols - 1)) / cols,
            ),
          ],
        );
      }),
    );
  }
}

class _SourcesSection extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      color: AppColors.bgSecondary,
      child: Column(
        children: [
          const Text('Площадки, которые мы агрегируем',
            style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800)),
          const SizedBox(height: 8),
          Text('Данные обновляются автоматически каждые 2 часа',
            style: TextStyle(color: AppColors.textSecondary, fontSize: 14)),
          const SizedBox(height: 24),
          Wrap(
            spacing: 12, runSpacing: 12,
            alignment: WrapAlignment.center,
            children: const [
              _SourceCard(name: 'ЕИС', count: '32 140', color: AppColors.sourceEis),
              _SourceCard(name: 'РТС-тендер', count: '8 420', color: AppColors.sourceRts),
              _SourceCard(name: 'Сбербанк-АСТ', count: '4 210', color: AppColors.sourceSber),
              _SourceCard(name: 'Корпоративные', count: '2 680', color: AppColors.sourceCorp),
              _SourceCard(name: 'Субподряды', count: '870', color: AppColors.sourceSub),
            ],
          ),
        ],
      ),
    );
  }
}

class _SourceCard extends StatelessWidget {
  final String name;
  final String count;
  final Color color;
  const _SourceCard({required this.name, required this.count, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 160, padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.card, border: Border.all(color: AppColors.border),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(width: 12, height: 12, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
          const SizedBox(height: 10),
          Text(name, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
          const SizedBox(height: 4),
          Text(count, style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900, color: AppColors.accent)),
          Text('тендеров', style: TextStyle(fontSize: 11, color: AppColors.textMuted)),
        ],
      ),
    );
  }
}
