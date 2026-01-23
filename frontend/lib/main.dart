import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'repositories/schedule_repository.dart';
import 'blocs/schedule_bloc.dart';
import 'ui/dashboard_screen.dart';
import 'firebase_options.dart';
import 'ui/theme/app_theme.dart'; 
import 'utils/security_utils.dart';

import 'ui/company_selection_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return RepositoryProvider(
      create: (context) => ScheduleRepository(),
      child: BlocProvider(
        create: (context) => ScheduleBloc(
          repository: context.read<ScheduleRepository>(),
        ),
        child: MaterialApp(
          title: 'PLANNER AI Scheduler',
          theme: AppTheme.darkTheme,
          debugShowCheckedModeBanner: false,
          home: const BootScreen(),
        ),
      ),
    );
  }
}

class BootScreen extends StatefulWidget {
  const BootScreen({super.key});

  @override
  State<BootScreen> createState() => _BootScreenState();
}

class _BootScreenState extends State<BootScreen> {
  bool _error = false;
  String _errorMessage = "";

  @override
  void initState() {
    super.initState();
    _initApp();
  }

  Future<void> _initApp() async {
    try {
      // 1. Initialize SharedPreferences & Session
      await SecurityUtils.init();
      
      // 2. Initialize Firebase
      await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);
      
      if (!mounted) return;

      // 3. Navigate to correct screen
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (context) => SecurityUtils.activeEnvironment.isNotEmpty
              ? const DashboardScreen()
              : const CompanySelectionScreen(),
        ),
      );
    } catch (e) {
      debugPrint("BOOT ERROR: $e");
      setState(() {
        _error = true;
        _errorMessage = e.toString();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Image.asset('assets/logo.png', height: 100),
            const SizedBox(height: 48),
            if (!_error) ...[
              const CircularProgressIndicator(color: AppTheme.aiGlow),
              const SizedBox(height: 24),
              const Text(
                "SINCRONIZZAZIONE SISTEMA...",
                style: TextStyle(color: Colors.white38, fontWeight: FontWeight.w900, letterSpacing: 2, fontSize: 10),
              ),
            ] else ...[
              const Icon(Icons.error_outline_rounded, color: Colors.redAccent, size: 48),
              const SizedBox(height: 24),
              const Text("ERRORE DI AVVIO", style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 40),
                child: Text(_errorMessage, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white38, fontSize: 12)),
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: () => _initApp(),
                child: const Text("RIPROVA"),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
