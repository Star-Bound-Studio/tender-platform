import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../models/models.dart';

class TenderCard extends StatelessWidget {
  final Tender tender;
  final VoidCallback? onTap;

  const TenderCard({super.key, required this.tender, this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          color: AppColors.card,
          border: Border.all(color: AppColors.border),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header: ID + source badge
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Flexible(
                  child: Text(
                    tender.sourceNumber,
                    style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppColors.accent, fontFamily: 'monospace'),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                _SourceBadge(
                  name: tender.sourceName ?? tender.sourceId,
                  color: AppColors.sourceColor(tender.sourceId),
                ),
              ],
            ),
            const SizedBox(height: 8),

            // Title
            Text(
              tender.title,
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, height: 1.4),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 6),

            // Customer
            if (tender.customerName != null)
              Text(
                tender.customerName!,
                style: const TextStyle(fontSize: 11, color: AppColors.textMuted),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),

            const SizedBox(height: 14),
            const Divider(height: 1),
            const SizedBox(height: 12),

            // Footer: price, region, type, deadline
            Wrap(
              spacing: 20,
              runSpacing: 8,
              children: [
                _FooterItem(label: 'НМЦ', value: tender.formattedPrice),
                if (tender.region != null)
                  _FooterItem(label: 'Регион', value: tender.region!),
                _FooterItem(label: 'Тип', value: _lawLabel(tender.lawType)),
              ],
            ),
          ],
        ),
      ),
    );
  }

  String _lawLabel(String law) {
    switch (law) {
      case '44-fz': return '44-ФЗ';
      case '223-fz': return '223-ФЗ';
      case 'commercial': return 'Коммерч.';
      case 'corporate': return 'Корпорат.';
      case 'subcontract': return 'Субподряд';
      default: return law;
    }
  }
}

class _SourceBadge extends StatelessWidget {
  final String name;
  final Color color;
  const _SourceBadge({required this.name, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
      decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(4)),
      child: Text(name, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: Colors.white)),
    );
  }
}

class _FooterItem extends StatelessWidget {
  final String label;
  final String value;
  const _FooterItem({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 9, color: AppColors.textMuted, letterSpacing: 0.3)),
        const SizedBox(height: 1),
        Text(value, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700)),
      ],
    );
  }
}
