import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../screens/home_screen.dart';
import '../screens/tenders_screen.dart';
import '../screens/tender_detail_screen.dart';
import '../screens/companies_screen.dart';
import '../screens/company_detail_screen.dart';
import '../screens/requests_screen.dart';
import '../screens/sources_screen.dart';
import '../screens/shell_screen.dart';

final router = GoRouter(
  initialLocation: '/',
  routes: [
    ShellRoute(
      builder: (context, state, child) => ShellScreen(child: child),
      routes: [
        GoRoute(
          path: '/',
          name: 'home',
          builder: (context, state) => const HomeScreen(),
        ),
        GoRoute(
          path: '/tenders',
          name: 'tenders',
          builder: (context, state) => const TendersScreen(),
          routes: [
            GoRoute(
              path: ':id',
              name: 'tender-detail',
              builder: (context, state) => TenderDetailScreen(
                tenderId: state.pathParameters['id']!,
              ),
            ),
          ],
        ),
        GoRoute(
          path: '/companies',
          name: 'companies',
          builder: (context, state) => const CompaniesScreen(),
          routes: [
            GoRoute(
              path: ':inn',
              name: 'company-detail',
              builder: (context, state) => CompanyDetailScreen(
                inn: state.pathParameters['inn']!,
              ),
            ),
          ],
        ),
        GoRoute(
          path: '/requests',
          name: 'requests',
          builder: (context, state) => const RequestsScreen(),
        ),
        GoRoute(
          path: '/sources',
          name: 'sources',
          builder: (context, state) => const SourcesScreen(),
        ),
      ],
    ),
  ],
);
