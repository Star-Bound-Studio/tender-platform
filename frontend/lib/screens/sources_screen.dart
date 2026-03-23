import 'package:flutter/material.dart';
import 'package:lucide_icons/lucide_icons.dart';
import '../theme/app_theme.dart';
import '../models/models.dart';
import '../services/api_service.dart';

class SourcesScreen extends StatefulWidget {
  const SourcesScreen({super.key});
  @override
  State<SourcesScreen> createState() => _SourcesScreenState();
}

class _SourcesScreenState extends State<SourcesScreen> {
  final _api = ApiService();
  List<TenderSource> _sources = [];
  bool _loading = true;

  @override
  void initState() { super.initState(); _load(); }
  Future<void> _load() async {
    try {
      final s = await _api.getSources();
      setState(() { _sources = s; _loading = false; });
    } catch (e) { setState(() => _loading = false); }
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(padding: const EdgeInsets.all(24), child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Подключенные площадки', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800)),
        const SizedBox(height: 8),
        const Text('Статус и статистика каждого источника данных', style: TextStyle(color: AppColors.textSecondary, fontSize: 14)),
        const SizedBox(height: 24),
        if (_loading) const Center(child: CircularProgressIndicator(color: AppColors.accent))
        else Wrap(spacing: 14, runSpacing: 14, children: _sources.map((s) => _SourceCard(source: s)).toList()),
      ],
    ));
  }
}

class _SourceCard extends StatelessWidget {
  final TenderSource source;
  const _SourceCard({required this.source});

  Color get _color {
    final c = source.color.replaceFirst('#', '');
    return Color(int.parse('FF$c', radix: 16));
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 280,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(color: AppColors.card, border: Border.all(color: AppColors.border), borderRadius: BorderRadius.circular(12)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(width: 14, height: 14, decoration: BoxDecoration(color: _color, shape: BoxShape.circle)),
          const SizedBox(width: 10),
          Flexible(child: Text(source.name, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700))),
        ]),
        const SizedBox(height: 14),
        Text('${source.tenderCount}', style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w900, color: AppColors.accent)),
        const Text('тендеров в базе', style: TextStyle(fontSize: 11, color: AppColors.textMuted)),
        const SizedBox(height: 14),
        const Divider(height: 1),
        const SizedBox(height: 10),
        Row(children: [
          Container(width: 8, height: 8, decoration: BoxDecoration(
            color: source.isActive ? const Color(0xFF22C55E) : AppColors.red, shape: BoxShape.circle)),
          const SizedBox(width: 6),
          Text(source.isActive ? 'Активен' : 'Отключен',
            style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: source.isActive ? const Color(0xFF22C55E) : AppColors.red)),
        ]),
      ]),
    );
  }
}
