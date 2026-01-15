import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../blocs/schedule_bloc.dart';
import '../repositories/schedule_repository.dart';
import 'calendar/calendar_grid.dart';
import 'widgets/ai_monitor_widget.dart';
import 'settings/demand_settings_dialog.dart';
import 'theme/app_theme.dart';
import '../utils/security_utils.dart';

import 'settings/developer_hub_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  List<String> _environments = [];
  bool _loadingEnvs = true;

  @override
  void initState() {
    super.initState();
    _fetchEnvs();
  }

  Future<void> _fetchEnvs() async {
    final envs = await context.read<ScheduleRepository>().getEnvironments();
    if (mounted) {
      setState(() {
        _environments = envs;
        _loadingEnvs = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        title: Row(
          children: [
            const Icon(Icons.rocket_launch_rounded, color: AppTheme.aiGlow),
            const SizedBox(width: 12),
            Text("TIMEPLANNER AI", style: Theme.of(context).appBarTheme.titleTextStyle),
          ],
        ),
        actions: [
          BlocBuilder<ScheduleBloc, ScheduleState>(
            builder: (context, state) {
              if (state is ScheduleLoaded && state.schedules.isNotEmpty) {
                return PopupMenuButton<String>(
                  icon: const Icon(Icons.download_rounded, color: AppTheme.textPrimary),
                  tooltip: "Export Schedule",
                  offset: const Offset(0, 50),
                  onSelected: (format) {
                    context.read<ScheduleRepository>().downloadReport(
                      format, 
                      state.schedules.first['schedule']
                    );
                  },
                  itemBuilder: (context) => [
                    const PopupMenuItem(value: "pdf", child: Text("Export as PDF")),
                    const PopupMenuItem(value: "csv", child: Text("Export as CSV")),
                    const PopupMenuItem(value: "ics", child: Text("Export as iCal (.ics)")),
                  ],
                );
              }
              return const SizedBox();
            },
          ),
          IconButton(
            icon: const Icon(Icons.tune_rounded, color: AppTheme.textPrimary),
            tooltip: "Demand Settings",
            onPressed: () {
              showDialog(
                context: context,
                builder: (context) => const DemandSettingsDialog(),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.refresh_rounded, color: AppTheme.textPrimary),
            onPressed: () => context.read<ScheduleBloc>().add(LoadInitialData()),
          ),
          const SizedBox(width: 10),
        ],
      ),
      body: Stack(
        children: [
          // Mesh Gradient Background
          Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [AppTheme.background, const Color(0xFF1E1B4B)],
              ),
            ),
          ),
          
          // Layout: Sidebar + Main Content
          Row(
            children: [
              // Sidebar (Glass)
              Container(
                width: 280,
                margin: const EdgeInsets.fromLTRB(20, 100, 0, 20),
                decoration: AppTheme.glassDecoration(),
                child: Padding(
                  padding: const EdgeInsets.all(24.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text("COMPANY / ENV", style: Theme.of(context).textTheme.titleSmall?.copyWith(color: AppTheme.textSecondary, letterSpacing: 1.5)),
                      const SizedBox(height: 12),
                      _loadingEnvs 
                        ? const LinearProgressIndicator(color: AppTheme.aiGlow)
                        : Container(
                            padding: const EdgeInsets.symmetric(horizontal: 12),
                            decoration: BoxDecoration(
                              color: Colors.white.withOpacity(0.05),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: DropdownButtonHideUnderline(
                              child: DropdownButton<String>(
                                value: SecurityUtils.activeEnvironment,
                                dropdownColor: const Color(0xFF1E1B4B),
                                isExpanded: true,
                                icon: const Icon(Icons.business_rounded, color: AppTheme.aiGlow),
                                items: _environments.map((env) {
                                  return DropdownMenuItem(
                                    value: env,
                                    child: Text(env, style: const TextStyle(color: Colors.white, fontSize: 13)),
                                  );
                                }).toList(),
                                onChanged: (val) {
                                  if (val != null) {
                                    setState(() => SecurityUtils.activeEnvironment = val);
                                    context.read<ScheduleBloc>().add(LoadInitialData());
                                  }
                                },
                              ),
                            ),
                          ),
                      const SizedBox(height: 32),
                      const AiMonitorWidget(),
                      const Spacer(),
                      
                      // Developer Access
                      InkWell(
                        onTap: () => Navigator.push(
                          context, 
                          MaterialPageRoute(builder: (_) => DeveloperHubScreen(repository: context.read<ScheduleRepository>()))
                        ),
                        child: Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            border: Border.all(color: Colors.white10),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Row(
                            children: [
                              const Icon(Icons.terminal_rounded, size: 18, color: Colors.blueAccent),
                              const SizedBox(width: 8),
                              Text("Developer Hub", style: TextStyle(color: Colors.grey.shade400, fontSize: 12)),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 24),
                      
                      Text("LEGEND", style: Theme.of(context).textTheme.titleSmall?.copyWith(color: AppTheme.textSecondary, letterSpacing: 1.5)),
                      const SizedBox(height: 16),
                      _buildLegendItem("Work Shift", AppTheme.primary),
                      _buildLegendItem("Unavailability", Colors.redAccent),
                      _buildLegendItem("AI Suggested", AppTheme.aiGlow),
                    ],
                  ),
                ),
              ),
              
              // Main Grid
              Expanded(
                child: BlocBuilder<ScheduleBloc, ScheduleState>(
                  builder: (context, state) {
                    if (state is ScheduleLoading) {
                      return Container(
                        color: AppTheme.background.withOpacity(0.95),
                        child: Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const SizedBox(
                                width: 80,
                                height: 80,
                                child: CircularProgressIndicator(
                                  color: AppTheme.aiGlow,
                                  strokeWidth: 6,
                                ),
                              ),
                              const SizedBox(height: 32),
                              const Text(
                                "AI sta lavorando...",
                                style: TextStyle(
                                  color: AppTheme.textPrimary,
                                  fontSize: 24,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              const SizedBox(height: 12),
                              Text(
                                "Generazione schedule per ${SecurityUtils.activeEnvironment}",
                                style: TextStyle(
                                  color: AppTheme.textSecondary,
                                  fontSize: 14,
                                ),
                              ),
                            ],
                          ),
                        ),
                      );
                    } else if (state is ScheduleError) {
                      return Center(child: Text("Error: ${state.message}", style: const TextStyle(color: Colors.redAccent)));
                    } else if (state is ScheduleLoaded) {
                      if (state.schedules.isEmpty) {
                        return Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(Icons.calendar_today_rounded, size: 64, color: AppTheme.textSecondary.withOpacity(0.3)),
                              const SizedBox(height: 16),
                              Text("No values found for ${SecurityUtils.activeEnvironment}", style: TextStyle(color: AppTheme.textSecondary)),
                            ],
                          ),
                        );
                      }
                      return CalendarGrid(scheduleData: state.schedules.first);
                    }
                    return const Center(child: Text("Initializing Engine..."));
                  },
                ),
              ),
            ],
          ),
        ],
      ),
      floatingActionButton: BlocBuilder<ScheduleBloc, ScheduleState>(
        builder: (context, state) {
          final isLoading = state is ScheduleLoading;
          return FloatingActionButton.extended(
            elevation: isLoading ? 0 : 4,
            backgroundColor: isLoading ? Colors.grey : AppTheme.aiGlow,
            onPressed: isLoading ? null : () {
              context.read<ScheduleBloc>().add(
                GenerateSchedules(
                  DateTime.now(), 
                  DateTime.now().add(const Duration(days: 7))
                )
              );
            },
            label: Text(
              isLoading ? "GENERAZIONE..." : "GENERA TURNI",
              style: const TextStyle(
                fontWeight: FontWeight.w900,
                color: Colors.white,
                letterSpacing: 0.5,
              ),
            ),
            icon: isLoading 
              ? const SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: Colors.white,
                  ),
                )
              : const Icon(Icons.auto_awesome, color: Colors.white),
          );
        },
      ),
    );
  }

  Widget _buildLegendItem(String label, Color color) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8.0),
      child: Row(
        children: [
          Container(
            width: 12,
            height: 12,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 12),
          Text(label, style: TextStyle(color: AppTheme.textPrimary, fontSize: 13, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }
}
