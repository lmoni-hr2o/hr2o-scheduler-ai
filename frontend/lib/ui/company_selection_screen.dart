import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../repositories/schedule_repository.dart';
import '../blocs/schedule_bloc.dart';
import '../utils/security_utils.dart';
import 'dashboard_screen.dart';
import 'theme/app_theme.dart';
import 'dart:ui';

class CompanySelectionScreen extends StatefulWidget {
  const CompanySelectionScreen({super.key});

  @override
  State<CompanySelectionScreen> createState() => _CompanySelectionScreenState();
}

class _CompanySelectionScreenState extends State<CompanySelectionScreen> {
  List<Map<String, String>> _environments = [];
  List<Map<String, String>> _filteredEnvironments = [];
  bool _isLoading = true;
  bool _isSyncing = false; // Added
  final TextEditingController _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadCompanies();
  }

  Future<void> _loadCompanies() async {
    try {
      final repo = context.read<ScheduleRepository>();
      final envs = await repo.getEnvironments();
      if (mounted) {
        setState(() {
          _environments = List<Map<String, String>>.from(envs);
          _filteredEnvironments = _environments;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("Error loading companies: $e")),
        );
      }
    }
  }

  void _filterCompanies(String query) {
    setState(() {
      _filteredEnvironments = _environments
          .where((env) =>
              (env['name'] ?? '').toLowerCase().contains(query.toLowerCase()) ||
              (env['id'] ?? '').toLowerCase().contains(query.toLowerCase()))
          .toList();
    });
  }



  void _selectCompany(Map<String, String> env) async {
    if (_isSyncing) return;
    
    setState(() => _isSyncing = true);
    await SecurityUtils.setActiveEnvironment(env['id']!);
    
    // Auto-Sync for fluid UX
    try {
      if (mounted) {
         // Use Repo to sync
         await context.read<ScheduleRepository>().syncOriginalSource();
      }
    } catch (e) {
      print("Auto-sync failed: $e");
    }

    if (mounted) {
      context.read<ScheduleBloc>().add(LoadInitialData());
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (context) => const DashboardScreen()),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      body: Stack(
        children: [
          // Background Gradient decoration
          Positioned(
            top: -100,
            right: -100,
            child: Container(
              width: 400,
              height: 400,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: AppTheme.aiGlow.withOpacity(0.05),
              ),
            ),
          ),
          Positioned(
            bottom: -150,
            left: -150,
            child: Container(
              width: 500,
              height: 500,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: AppTheme.primary.withOpacity(0.05),
              ),
            ),
          ),
          
          Center(
            child: Container(
              width: 500,
              padding: const EdgeInsets.all(40),
              decoration: AppTheme.glassDecoration(),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Image.asset('assets/logo.png', height: 80),
                  const SizedBox(height: 30),
                  const Text(
                    "BENVENUTO",
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 28,
                      fontWeight: FontWeight.w900,
                      letterSpacing: 2,
                    ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    "Seleziona l'azienda per iniziare a pianificare",
                    style: TextStyle(
                      color: AppTheme.textSecondary,
                      fontSize: 14,
                    ),
                  ),
                  const SizedBox(height: 40),
                  
                  // Search Bar
                  TextField(
                    controller: _searchController,
                    onChanged: _filterCompanies,
                    style: const TextStyle(color: Colors.white),
                    decoration: InputDecoration(
                      hintText: "Cerca azienda...",
                      hintStyle: TextStyle(color: Colors.white.withOpacity(0.3)),
                      prefixIcon: const Icon(Icons.search_rounded, color: AppTheme.aiGlow),
                      filled: true,
                      fillColor: Colors.white.withOpacity(0.05),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(15),
                        borderSide: BorderSide.none,
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),
                  
                  // Company List
                  Container(
                    height: 300,
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.02),
                      borderRadius: BorderRadius.circular(15),
                      border: Border.all(color: Colors.white.withOpacity(0.05)),
                    ),
                    child: _isSyncing
                        ? const Center(
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                CircularProgressIndicator(color: AppTheme.accent),
                                SizedBox(height: 16),
                                Text(
                                  "Sincronizzazione dati in corso...", 
                                  style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)
                                ),
                                SizedBox(height: 8),
                                Text(
                                  "Potrebbe richiedere fino a 30 secondi", 
                                  style: TextStyle(color: Colors.white54, fontSize: 12)
                                ),
                              ],
                            ),
                          )
                        : _isLoading
                        ? const Center(child: CircularProgressIndicator(color: AppTheme.aiGlow))
                        : _filteredEnvironments.isEmpty
                            ? const Center(child: Text("Nessuna azienda trovata", style: TextStyle(color: Colors.white38)))
                            : ListView.separated(
                                padding: const EdgeInsets.all(10),
                                itemCount: _filteredEnvironments.length,
                                separatorBuilder: (context, index) => const Divider(height: 1, color: Colors.white10),
                                itemBuilder: (context, index) {
                                  final env = _filteredEnvironments[index];
                                  return ListTile(
                                    contentPadding: const EdgeInsets.symmetric(horizontal: 15, vertical: 5),
                                    leading: CircleAvatar(
                                      backgroundColor: AppTheme.aiGlow.withOpacity(0.1),
                                      child: const Icon(Icons.business_rounded, color: AppTheme.aiGlow, size: 20),
                                    ),
                                    title: Text(
                                      env['name'] ?? env['id'] ?? "Unknown",
                                      style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                                    ),
                                    subtitle: Text(
                                      "ID: ${env['id']}",
                                      style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 11),
                                    ),
                                    trailing: const Icon(Icons.arrow_forward_ios_rounded, color: Colors.white24, size: 14),
                                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                                    onTap: () => _selectCompany(env),
                                  );
                                },
                              ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
