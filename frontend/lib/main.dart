import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'theme/app_theme.dart';
import 'services/router.dart';

void main() {
  runApp(const ProviderScope(child: TenderPlatformApp()));
}

class TenderPlatformApp extends StatelessWidget {
  const TenderPlatformApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'Tender Platform',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.dark,
      routerConfig: router,
    );
  }
}
