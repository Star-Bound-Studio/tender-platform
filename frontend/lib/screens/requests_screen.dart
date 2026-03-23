import 'package:flutter/material.dart';
import 'package:lucide_icons/lucide_icons.dart';
import '../theme/app_theme.dart';
import '../models/models.dart';
import '../services/api_service.dart';

class RequestsScreen extends StatefulWidget {
  const RequestsScreen({super.key});
  @override
  State<RequestsScreen> createState() => _RequestsScreenState();
}

class _RequestsScreenState extends State<RequestsScreen> {
  final _api = ApiService();
  List<SubcontractRequest> _requests = [];
  bool _loading = true;

  @override
  void initState() { super.initState(); _load(); }
  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final resp = await _api.getRequests();
      final items = (resp['items'] as List).map((e) => SubcontractRequest.fromJson(e)).toList();
      setState(() { _requests = items; _loading = false; });
    } catch (e) { setState(() => _loading = false); }
  }

  @override
  Widget build(BuildContext context) {
    return CustomScrollView(slivers: [
      SliverToBoxAdapter(child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
            const Text('Заявки на субподряд', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800)),
            ElevatedButton.icon(
              onPressed: () { /* TODO: create request dialog */ },
              icon: const Icon(LucideIcons.plus, size: 16),
              label: const Text('Разместить'),
            ),
          ]),
          const SizedBox(height: 8),
          Text('${_requests.length} заявок', style: const TextStyle(fontSize: 12, color: AppColors.textMuted)),
        ]),
      )),
      _loading
        ? const SliverFillRemaining(child: Center(child: CircularProgressIndicator(color: AppColors.accent)))
        : SliverPadding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            sliver: SliverList.separated(
              itemCount: _requests.length,
              separatorBuilder: (_, __) => const SizedBox(height: 10),
              itemBuilder: (_, i) {
                final r = _requests[i];
                return Container(
                  padding: const EdgeInsets.all(18),
                  decoration: BoxDecoration(color: AppColors.card, border: Border.all(color: AppColors.border), borderRadius: BorderRadius.circular(12)),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                      Flexible(child: Text(r.title, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: AppColors.accent))),
                      if (r.category != null) Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(color: AppColors.pink, borderRadius: BorderRadius.circular(4)),
                        child: Text(r.category!, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: Colors.white)),
                      ),
                    ]),
                    if (r.description != null) ...[
                      const SizedBox(height: 8),
                      Text(r.description!, style: const TextStyle(fontSize: 13, color: AppColors.textSecondary, height: 1.5), maxLines: 3, overflow: TextOverflow.ellipsis),
                    ],
                    const SizedBox(height: 12),
                    const Divider(height: 1),
                    const SizedBox(height: 10),
                    Wrap(spacing: 16, children: [
                      if (r.budgetText != null) Text('Бюджет: ${r.budgetText}', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                      if (r.region != null) Text(r.region!, style: const TextStyle(fontSize: 12, color: AppColors.textMuted)),
                    ]),
                  ]),
                );
              },
            ),
          ),
      const SliverToBoxAdapter(child: SizedBox(height: 32)),
    ]);
  }
}
