import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class StatCard extends StatelessWidget {
  final String value;
  final String label;
  const StatCard({super.key, required this.value, required this.label});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(value, style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w900, color: AppColors.accent)),
        Text(label, style: const TextStyle(fontSize: 10, color: AppColors.textMuted, letterSpacing: 1)),
      ],
    );
  }
}
