import 'package:flutter/material.dart';
import 'package:lucide_icons/lucide_icons.dart';
import '../theme/app_theme.dart';
import '../models/models.dart';
import '../services/api_service.dart';

class CompanyDetailScreen extends StatefulWidget {
  final String inn;
  const CompanyDetailScreen({super.key, required this.inn});
  @override
  State<CompanyDetailScreen> createState() => _CompanyDetailState();
}

class _CompanyDetailState extends State<CompanyDetailScreen> {
  final _api = ApiService();
  Company? _company;
  bool _loading = true;

  @override
  void initState() { super.initState(); _load(); }
  Future<void> _load() async {
    try {
      final c = await _api.getCompany(widget.inn);
      setState(() { _company = c; _loading = false; });
    } catch (e) { setState(() => _loading = false); }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator(color: AppColors.accent));
    if (_company == null) return const Center(child: Text('Компания не найдена'));
    final c = _company!;

    return SingleChildScrollView(padding: const EdgeInsets.all(24), child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(c.fullName, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
        const SizedBox(height: 4),
        if (c.region != null) Text(c.region!, style: const TextStyle(color: AppColors.textSecondary)),
        const SizedBox(height: 20),
        // Stats row
        Wrap(spacing: 12, runSpacing: 12, children: [
          _StatBox(label: 'Тендеров', value: '${c.tenderWinsCount}', icon: LucideIcons.trophy),
          _StatBox(label: 'Арбитраж', value: '${c.arbitrationCount}', icon: LucideIcons.scale),
          if (c.hasSro) _StatBox(label: 'СРО', value: 'Есть', icon: LucideIcons.shieldCheck),
        ]),
        const SizedBox(height: 24),
        // Details
        _Section(title: 'Реквизиты', children: [
          _Row('ИНН', c.inn),
          if (c.ogrn != null) _Row('ОГРН', c.ogrn!),
          if (c.directorName != null) _Row('Руководитель', c.directorName!),
          if (c.primaryOkved != null) _Row('Основной ОКВЭД', c.primaryOkved!),
        ]),
        // Financials
        if (c.financials != null && c.financials!.isNotEmpty) ...[
          const SizedBox(height: 20),
          _Section(title: 'Финансы', children: c.financials!.map((f) =>
            _Row('${f.year}', '${f.formattedRevenue} выручка${f.employees != null ? ", ${f.employees} чел." : ""}')
          ).toList()),
        ],
        // SRO
        if (c.sroPermits != null && c.sroPermits!.isNotEmpty) ...[
          const SizedBox(height: 20),
          _Section(title: 'Допуски СРО', children: c.sroPermits!.map((s) =>
            _Row(s.sroName, s.status)
          ).toList()),
        ],
      ],
    ));
  }
}

class _StatBox extends StatelessWidget {
  final String label, value;
  final IconData icon;
  const _StatBox({required this.label, required this.value, required this.icon});
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(color: AppColors.card, border: Border.all(color: AppColors.border), borderRadius: BorderRadius.circular(10)),
    child: Row(mainAxisSize: MainAxisSize.min, children: [
      Icon(icon, size: 18, color: AppColors.accent),
      const SizedBox(width: 8),
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(value, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: AppColors.accent)),
        Text(label, style: const TextStyle(fontSize: 10, color: AppColors.textMuted)),
      ]),
    ]),
  );
}

class _Section extends StatelessWidget {
  final String title;
  final List<Widget> children;
  const _Section({required this.title, required this.children});
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
      const SizedBox(height: 10),
      ...children,
    ],
  );
}

class _Row extends StatelessWidget {
  final String label, value;
  const _Row(this.label, this.value);
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 6),
    child: Row(children: [
      SizedBox(width: 140, child: Text(label, style: const TextStyle(fontSize: 13, color: AppColors.textMuted))),
      Flexible(child: Text(value, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600))),
    ]),
  );
}
