import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons/lucide_icons.dart';
import '../theme/app_theme.dart';

class ShellScreen extends StatelessWidget {
  final Widget child;
  const ShellScreen({super.key, required this.child});

  int _currentIndex(BuildContext context) {
    final location = GoRouterState.of(context).uri.toString();
    if (location.startsWith('/tenders')) return 1;
    if (location.startsWith('/companies')) return 2;
    if (location.startsWith('/requests')) return 3;
    if (location.startsWith('/sources')) return 4;
    return 0;
  }

  @override
  Widget build(BuildContext context) {
    final index = _currentIndex(context);
    final isWide = MediaQuery.of(context).size.width > 900;

    return Scaffold(
      body: Row(
        children: [
          // Desktop side nav
          if (isWide)
            NavigationRail(
              backgroundColor: AppColors.bgSecondary,
              selectedIndex: index,
              onDestinationSelected: (i) => _navigate(context, i),
              labelType: NavigationRailLabelType.all,
              leading: Padding(
                padding: const EdgeInsets.symmetric(vertical: 16),
                child: _Logo(),
              ),
              selectedIconTheme: const IconThemeData(color: AppColors.accent),
              unselectedIconTheme: const IconThemeData(color: AppColors.textMuted),
              selectedLabelTextStyle: const TextStyle(color: AppColors.accent, fontSize: 11, fontWeight: FontWeight.w600),
              unselectedLabelTextStyle: const TextStyle(color: AppColors.textMuted, fontSize: 11),
              destinations: const [
                NavigationRailDestination(icon: Icon(LucideIcons.home), label: Text('Главная')),
                NavigationRailDestination(icon: Icon(LucideIcons.fileText), label: Text('Тендеры')),
                NavigationRailDestination(icon: Icon(LucideIcons.building2), label: Text('Компании')),
                NavigationRailDestination(icon: Icon(LucideIcons.clipboardList), label: Text('Заявки')),
                NavigationRailDestination(icon: Icon(LucideIcons.radio), label: Text('Площадки')),
              ],
            ),
          // Main content
          Expanded(child: child),
        ],
      ),
      // Mobile bottom nav
      bottomNavigationBar: isWide ? null : BottomNavigationBar(
        currentIndex: index,
        onTap: (i) => _navigate(context, i),
        items: const [
          BottomNavigationBarItem(icon: Icon(LucideIcons.home), label: 'Главная'),
          BottomNavigationBarItem(icon: Icon(LucideIcons.fileText), label: 'Тендеры'),
          BottomNavigationBarItem(icon: Icon(LucideIcons.building2), label: 'Компании'),
          BottomNavigationBarItem(icon: Icon(LucideIcons.clipboardList), label: 'Заявки'),
          BottomNavigationBarItem(icon: Icon(LucideIcons.radio), label: 'Площадки'),
        ],
      ),
    );
  }

  void _navigate(BuildContext context, int index) {
    switch (index) {
      case 0: context.go('/');
      case 1: context.go('/tenders');
      case 2: context.go('/companies');
      case 3: context.go('/requests');
      case 4: context.go('/sources');
    }
  }
}

class _Logo extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      width: 40, height: 40,
      decoration: BoxDecoration(
        gradient: const LinearGradient(colors: [AppColors.accent, Color(0xFF00896E)]),
        borderRadius: BorderRadius.circular(10),
      ),
      child: const Center(
        child: Text('AG', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w900, fontSize: 14)),
      ),
    );
  }
}
