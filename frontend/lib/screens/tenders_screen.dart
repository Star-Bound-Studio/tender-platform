import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons/lucide_icons.dart';
import '../theme/app_theme.dart';
import '../models/models.dart';
import '../services/api_service.dart';
import '../widgets/tender_card.dart';
import '../widgets/source_badge.dart';

class TendersScreen extends StatefulWidget {
  const TendersScreen({super.key});
  @override
  State<TendersScreen> createState() => _TendersScreenState();
}

class _TendersScreenState extends State<TendersScreen> {
  final _api = ApiService();
  final _searchCtrl = TextEditingController();
  
  List<Tender> _tenders = [];
  Map<String, int> _sourceCounts = {};
  int _total = 0;
  bool _loading = true;
  String? _selectedSource;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final resp = await _api.getTenders(
        q: _searchCtrl.text.isNotEmpty ? _searchCtrl.text : null,
        sourceId: _selectedSource,
      );
      setState(() {
        _tenders = resp.items;
        _sourceCounts = resp.sourceCounts;
        _total = resp.total;
        _loading = false;
      });
    } catch (e) {
      setState(() => _loading = false);
      // TODO: show error
    }
  }

  @override
  Widget build(BuildContext context) {
    return CustomScrollView(
      slivers: [
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Тендеры и закупки', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800)),
                const SizedBox(height: 16),
                // Search bar
                TextField(
                  controller: _searchCtrl,
                  decoration: InputDecoration(
                    hintText: 'Поиск по названию, ОКВЭД, заказчику...',
                    prefixIcon: const Icon(LucideIcons.search, size: 18),
                    suffixIcon: IconButton(
                      icon: const Icon(LucideIcons.arrowRight, size: 18),
                      onPressed: _load,
                    ),
                  ),
                  onSubmitted: (_) => _load(),
                ),
                const SizedBox(height: 16),
                // Source count badges
                Wrap(
                  spacing: 6, runSpacing: 6,
                  children: [
                    _CountChip(label: 'Всего', count: _total, selected: _selectedSource == null,
                      onTap: () { setState(() => _selectedSource = null); _load(); }),
                    ..._sourceCounts.entries.map((e) => _CountChip(
                      label: _sourceName(e.key), count: e.value, color: AppColors.sourceColor(e.key),
                      selected: _selectedSource == e.key,
                      onTap: () { setState(() => _selectedSource = _selectedSource == e.key ? null : e.key); _load(); },
                    )),
                  ],
                ),
                const SizedBox(height: 8),
                Text('Показано: ${_tenders.length} из $_total', style: const TextStyle(fontSize: 12, color: AppColors.textMuted)),
              ],
            ),
          ),
        ),
        // Tender list
        _loading
          ? const SliverFillRemaining(child: Center(child: CircularProgressIndicator(color: AppColors.accent)))
          : SliverPadding(
              padding: const EdgeInsets.symmetric(horizontal: 24),
              sliver: SliverList.separated(
                itemCount: _tenders.length,
                separatorBuilder: (_, __) => const SizedBox(height: 10),
                itemBuilder: (context, index) {
                  final t = _tenders[index];
                  return TenderCard(
                    tender: t,
                    onTap: () => context.go('/tenders/${t.id}'),
                  );
                },
              ),
            ),
        const SliverToBoxAdapter(child: SizedBox(height: 32)),
      ],
    );
  }

  String _sourceName(String id) {
    const map = {'eis': 'ЕИС', 'rts': 'РТС', 'sber': 'Сбер-АСТ', 'rosneft': 'Роснефть', 'gazprom': 'Газпром', 'vsem_podryad': 'Субподряды'};
    return map[id] ?? id;
  }
}

class _CountChip extends StatelessWidget {
  final String label;
  final int count;
  final Color? color;
  final bool selected;
  final VoidCallback onTap;

  const _CountChip({required this.label, required this.count, this.color, this.selected = false, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
        decoration: BoxDecoration(
          color: selected ? AppColors.accentGlow : AppColors.bgSecondary,
          border: Border.all(color: selected ? AppColors.accent : AppColors.border),
          borderRadius: BorderRadius.circular(6),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          if (color != null) ...[
            Container(width: 6, height: 6, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
            const SizedBox(width: 5),
          ],
          Text('$label: ', style: const TextStyle(fontSize: 11, color: AppColors.textSecondary)),
          Text('$count', style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700)),
        ]),
      ),
    );
  }
}
