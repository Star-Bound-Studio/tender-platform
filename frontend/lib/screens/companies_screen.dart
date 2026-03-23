import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons/lucide_icons.dart';
import '../theme/app_theme.dart';
import '../models/models.dart';
import '../services/api_service.dart';

class CompaniesScreen extends StatefulWidget {
  const CompaniesScreen({super.key});
  @override
  State<CompaniesScreen> createState() => _CompaniesScreenState();
}

class _CompaniesScreenState extends State<CompaniesScreen> {
  final _api = ApiService();
  final _searchCtrl = TextEditingController();
  List<Company> _companies = [];
  int _total = 0;
  bool _loading = true;

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final resp = await _api.getCompanies(q: _searchCtrl.text.isNotEmpty ? _searchCtrl.text : null);
      final items = (resp['items'] as List).map((e) => Company.fromJson(e)).toList();
      setState(() { _companies = items; _total = resp['total'] ?? 0; _loading = false; });
    } catch (e) { setState(() => _loading = false); }
  }

  @override
  Widget build(BuildContext context) {
    return CustomScrollView(slivers: [
      SliverToBoxAdapter(child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Справочник компаний', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800)),
          const SizedBox(height: 16),
          TextField(
            controller: _searchCtrl,
            decoration: InputDecoration(
              hintText: 'Поиск по названию, ИНН, ОКВЭД...',
              prefixIcon: const Icon(LucideIcons.search, size: 18),
            ),
            onSubmitted: (_) => _load(),
          ),
          const SizedBox(height: 12),
          Text('Найдено: ${_companies.length} из $_total', style: const TextStyle(fontSize: 12, color: AppColors.textMuted)),
        ]),
      )),
      _loading
        ? const SliverFillRemaining(child: Center(child: CircularProgressIndicator(color: AppColors.accent)))
        : SliverPadding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            sliver: SliverList.separated(
              itemCount: _companies.length,
              separatorBuilder: (_, __) => const SizedBox(height: 10),
              itemBuilder: (_, i) {
                final c = _companies[i];
                return _CompanyCard(company: c, onTap: () => context.go('/companies/${c.inn}'));
              },
            ),
          ),
      const SliverToBoxAdapter(child: SizedBox(height: 32)),
    ]);
  }
}

class _CompanyCard extends StatelessWidget {
  final Company company;
  final VoidCallback? onTap;
  const _CompanyCard({required this.company, this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(color: AppColors.card, border: Border.all(color: AppColors.border), borderRadius: BorderRadius.circular(12)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
            Flexible(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Flexible(child: Text(company.fullName, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700))),
                if (company.hasSro) ...[const SizedBox(width: 6), const Text('SRO', style: TextStyle(fontSize: 11, color: AppColors.accent, fontWeight: FontWeight.w700))],
              ]),
              if (company.primaryOkved != null)
                Text('ОКВЭД: ${company.primaryOkved}', style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
            ])),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(color: AppColors.accentGlow, borderRadius: BorderRadius.circular(6)),
              child: Text('${company.tenderWinsCount}', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: AppColors.accent)),
            ),
          ]),
          const SizedBox(height: 10),
          const Divider(height: 1),
          const SizedBox(height: 8),
          Wrap(spacing: 14, runSpacing: 4, children: [
            if (company.region != null) Text(company.region!, style: const TextStyle(fontSize: 11, color: AppColors.textMuted)),
            Text('ИНН: ${company.inn}', style: const TextStyle(fontSize: 11, color: AppColors.textMuted)),
          ]),
        ]),
      ),
    );
  }
}
