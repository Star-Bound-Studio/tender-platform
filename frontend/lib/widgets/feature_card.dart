import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class FeatureCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String description;
  final bool highlighted;
  final VoidCallback? onTap;
  final double? width;

  const FeatureCard({
    super.key, required this.icon, required this.title, required this.description,
    this.highlighted = false, this.onTap, this.width,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: width,
        padding: const EdgeInsets.all(22),
        decoration: BoxDecoration(
          color: highlighted ? AppColors.accent.withOpacity(0.08) : AppColors.card,
          border: Border.all(color: highlighted ? AppColors.accent.withOpacity(0.25) : AppColors.border),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 44, height: 44,
              decoration: BoxDecoration(
                color: AppColors.accentGlow,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, size: 20, color: AppColors.accent),
            ),
            const SizedBox(height: 14),
            Text(title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
            const SizedBox(height: 6),
            Text(description, style: const TextStyle(fontSize: 13, color: AppColors.textSecondary, height: 1.5)),
          ],
        ),
      ),
    );
  }
}
