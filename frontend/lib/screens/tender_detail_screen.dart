import 'package:flutter/material.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:url_launcher/url_launcher.dart';
import '../theme/app_theme.dart';
import '../models/models.dart';
import '../services/api_service.dart';

class TenderDetailScreen extends StatefulWidget {
  final String tenderId;
  const TenderDetailScreen({super.key, required this.tenderId});
  @override
  State<TenderDetailScreen> createState() => _TenderDetailState();
}

class _TenderDetailState extends State<TenderDetailScreen> {
  final _api = ApiService();
  Tender? _tender;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final t = await _api.getTender(widget.tenderId);
      setState(() { _tender = t; _loading = false; });
    } catch (e) {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator(color: AppColors.accent));
    if (_tender == null) return const Center(child: Text('Тендер не найден'));

    final t = _tender!;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Source badge + ID
          Row(children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(color: AppColors.sourceColor(t.sourceId), borderRadius: BorderRadius.circular(4)),
              child: Text(t.sourceName ?? t.sourceId, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: Colors.white)),
            ),
            const SizedBox(width: 10),
            Text(t.sourceNumber, style: const TextStyle(fontSize: 13, color: AppColors.accent, fontFamily: 'monospace')),
          ]),
          const SizedBox(height: 16),

          Text(t.title, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800, height: 1.3)),
          const SizedBox(height: 12),

          if (t.customerName != null)
            _InfoRow(icon: LucideIcons.building2, label: 'Заказчик', value: t.customerName!),
          if (t.region != null)
            _InfoRow(icon: LucideIcons.mapPin, label: 'Регион', value: t.region!),
          _InfoRow(icon: LucideIcons.banknote, label: 'НМЦ', value: t.formattedPrice),
          _InfoRow(icon: LucideIcons.scale, label: 'Тип', value: t.lawType),

          const SizedBox(height: 20),
          if (t.description != null) ...[
            const Text('Описание', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            Text(t.description!, style: const TextStyle(fontSize: 14, color: AppColors.textSecondary, height: 1.6)),
            const SizedBox(height: 20),
          ],

          // Link to original
          if (t.sourceUrl != null)
            ElevatedButton.icon(
              onPressed: () => launchUrl(Uri.parse(t.sourceUrl!)),
              icon: const Icon(LucideIcons.externalLink, size: 16),
              label: const Text('Перейти на площадку'),
            ),
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  const _InfoRow({required this.icon, required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(children: [
        Icon(icon, size: 16, color: AppColors.textMuted),
        const SizedBox(width: 8),
        Text('$label: ', style: const TextStyle(fontSize: 13, color: AppColors.textMuted)),
        Flexible(child: Text(value, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600))),
      ]),
    );
  }
}
