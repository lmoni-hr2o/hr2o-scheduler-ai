import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'repositories/schedule_repository.dart';
import 'blocs/schedule_bloc.dart';
import 'ui/dashboard_screen.dart';
import 'firebase_options.dart';
import 'ui/theme/app_theme.dart'; // Added import

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Initialize Firebase using the generated options
  await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform); 


  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return RepositoryProvider(
      create: (context) => ScheduleRepository(
        companyId: "hr2o_development", // Replaced 'company_123' with a meaningful project identifier
      ),
      child: BlocProvider(
        create: (context) => ScheduleBloc(
          repository: context.read<ScheduleRepository>(),
        ),
        child: MaterialApp(
          title: 'PLANNER AI Scheduler',
          theme: AppTheme.darkTheme, // Replaced ThemeData with AppTheme.darkTheme
          home: const DashboardScreen(),
        ),
      ),
    );
  }
}
