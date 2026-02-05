import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../blocs/schedule_bloc.dart';
import '../repositories/schedule_repository.dart';
import 'calendar/calendar_grid.dart';
import 'widgets/ai_monitor_widget.dart';
import 'widgets/ai_report_dialog.dart';
import 'widgets/ai_advisor_dialog.dart';
import 'settings/demand_settings_dialog.dart';
import 'theme/app_theme.dart';
import '../utils/security_utils.dart';

import 'settings/ai_engine_monitor_screen.dart';
import 'company_selection_screen.dart';
import 'labor_profiles_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  // Navigation State
  DateTime _visibleWeekStart = _getStartOfWeek(DateTime.now());

  static DateTime _getStartOfWeek(DateTime date) {
    return date.subtract(Duration(days: date.weekday - 1));
  }

  void _navigateWeek(int weeks) {
    setState(() {
      _visibleWeekStart = _visibleWeekStart.add(Duration(days: 7 * weeks));
    });
  }

  @override
  void initState() {
    super.initState();
    // Load data for the already selected active environment
    context.read<ScheduleBloc>().add(LoadInitialData());
  }

  @override
  Widget build(BuildContext context) {
    // Determine the end date of the visible week for display
    final visibleWeekEnd = _visibleWeekStart.add(const Duration(days: 6));
    final dateFormat = DateFormat('dd MMM yyyy');

    return Scaffold(
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        title: Row(
          children: [
            Image.asset(
              'assets/logo.png',
              height: 50,
              filterQuality: FilterQuality.high,
            ),
            const SizedBox(width: 12),
            Text("TIMEPLANNER AI", style: Theme.of(context).appBarTheme.titleTextStyle),
            const SizedBox(width: 8),
            IconButton(
              icon: const Icon(Icons.logout_rounded, color: Colors.white38, size: 20),
              tooltip: "Torna alla selezione azienda",
              onPressed: () async {
                await SecurityUtils.setActiveEnvironment("");
                if (mounted) {
                  Navigator.pushReplacement(
                    context,
                    MaterialPageRoute(builder: (context) => const CompanySelectionScreen()),
                  );
                }
              },
            ),
          ],
        ),
        actions: [
          BlocBuilder<ScheduleBloc, ScheduleState>(
            builder: (context, state) {
              if (state is ScheduleLoaded && state.schedules.isNotEmpty) {
                 return Padding(
                   padding: const EdgeInsets.only(right: 8.0),
                   child: ElevatedButton.icon(
                     style: ElevatedButton.styleFrom(
                       backgroundColor: AppTheme.aiGlow.withOpacity(0.2),
                       side: const BorderSide(color: AppTheme.aiGlow),
                     ),
                     icon: const Icon(Icons.psychology, color: Colors.white, size: 18),
                     label: const Text("AI REPORT", style: TextStyle(color: Colors.white)),
                     onPressed: () {
                       showDialog(
                         context: context,
                         builder: (_) => AiReportDialog(
                           schedule: state.schedules.first['schedule'],
                           startDate: _visibleWeekStart,
                           endDate: visibleWeekEnd,
                         ),
                       );
                     },
                   ),
                 );
              }
              return const SizedBox();
            },
          ),
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
            icon: const Icon(Icons.assignment_ind_rounded, color: AppTheme.textPrimary),
            tooltip: "Profili Lavorativi",
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => LaborProfilesScreen()),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.psychology_rounded, color: AppTheme.aiGlow),
            tooltip: "Neural Engine Monitor",
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => AiEngineMonitorScreen(
                  repository: context.read<ScheduleRepository>()
                )),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.tune_rounded, color: AppTheme.textPrimary),
            tooltip: "AI Settings",
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
          // Deep Cyber Background
          Container(
            decoration: const BoxDecoration(
              gradient: RadialGradient(
                center: Alignment(0.0, -0.4),
                radius: 1.5,
                colors: [
                  Color(0xFF1E1B4B), // Deep Indigo Glow
                  AppTheme.background, // Abyss
                ],
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
                      const SizedBox(height: 32),
                      Text("ACTIVE COMPANY", style: Theme.of(context).textTheme.titleSmall?.copyWith(color: AppTheme.textSecondary, letterSpacing: 1.5)),
                      const SizedBox(height: 12),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: AppTheme.aiGlow.withOpacity(0.05),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: AppTheme.aiGlow.withOpacity(0.1)),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.business_rounded, color: AppTheme.aiGlow, size: 20),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                SecurityUtils.activeEnvironment,
                                style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                            IconButton(
                              icon: const Icon(Icons.swap_horiz_rounded, color: Colors.white60, size: 20),
                              onPressed: () {
                                Navigator.pushReplacement(
                                  context,
                                  MaterialPageRoute(builder: (context) => const CompanySelectionScreen()),
                                );
                              },
                              tooltip: "Change Company",
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 32),
                      const AiMonitorWidget(),
                      const Spacer(),
                      
                      const SizedBox(height: 24),
                      
                      Text("LEGEND", style: Theme.of(context).textTheme.titleSmall?.copyWith(color: AppTheme.textSecondary, letterSpacing: 1.5)),
                      const SizedBox(height: 16),
                      _buildLegendItem("Work Shift", AppTheme.primary),
                      _buildLegendItem("Unavailability", Colors.redAccent),
                      _buildLegendItem("High Risk Abs.", Colors.orange),
                    ],
                  ),
                ),
              ),
              
              // Main Grid
              Expanded(
                child: Column(
                  children: [
                    // Navigation Bar
                    Padding(
                      padding: const EdgeInsets.fromLTRB(20, 100, 20, 0),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          IconButton(
                            icon: const Icon(Icons.arrow_back_ios_rounded, color: Colors.white70),
                            onPressed: () => _navigateWeek(-1),
                            tooltip: "Previous Week",
                          ),
                          const SizedBox(width: 16),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 8),
                            decoration: BoxDecoration(
                              color: Colors.white.withOpacity(0.05),
                              borderRadius: BorderRadius.circular(20),
                              border: Border.all(color: Colors.white.withOpacity(0.1)),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.calendar_today_rounded, color: AppTheme.aiGlow, size: 16),
                                const SizedBox(width: 12),
                                Text(
                                  "${dateFormat.format(_visibleWeekStart)} - ${dateFormat.format(visibleWeekEnd)}",
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 16,
                                    fontWeight: FontWeight.bold,
                                    letterSpacing: 1.0,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(width: 16),
                          IconButton(
                            icon: const Icon(Icons.arrow_forward_ios_rounded, color: Colors.white70),
                            onPressed: () => _navigateWeek(1),
                            tooltip: "Next Week",
                          ),
                        ],
                      ),
                    ),
                    
                    // The Grid
                    Expanded(
                      child: BlocBuilder<ScheduleBloc, ScheduleState>(
                        builder: (context, state) {
                          if (state is ScheduleLoading) {
                            return Container(
                              margin: const EdgeInsets.fromLTRB(20, 20, 20, 20), // Adjusted margins
                              decoration: AppTheme.glassDecoration(), // Keep style consistent
                              child: Center(
                                child: Column(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    const SizedBox(
                                      width: 60,
                                      height: 60,
                                      child: CircularProgressIndicator(
                                        color: AppTheme.aiGlow,
                                        strokeWidth: 4,
                                      ),
                                    ),
                                    const SizedBox(height: 24),
                                    Text(
                                      state.message ?? "AI sta lavorando...",
                                      style: const TextStyle(
                                        color: AppTheme.textPrimary,
                                        fontSize: 18,
                                        fontWeight: FontWeight.bold,
                                      ),
                                      textAlign: TextAlign.center,
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
                            return CalendarGrid(
                              scheduleData: state.schedules.first,
                              startDate: _visibleWeekStart, // Pass navigation state
                            );
                          }
                          return const Center(child: Text("Initializing Engine..."));
                        },
                      ),
                    ),
                  ],
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
            onPressed: isLoading ? null : () async {
              // 1. Show Date Picker
              final DateTime? picked = await showDatePicker(
                context: context,
                initialDate: _visibleWeekStart, // Suggest current view
                firstDate: DateTime.now().subtract(const Duration(days: 365)),
                lastDate: DateTime.now().add(const Duration(days: 365)),
                builder: (context, child) {
                  return Theme(
                    data: ThemeData.dark().copyWith(
                      colorScheme: const ColorScheme.dark(
                        primary: AppTheme.aiGlow,
                        onPrimary: Colors.white,
                        surface: Color(0xFF1E1B4B),
                        onSurface: Colors.white,
                      ),
                      dialogBackgroundColor: const Color(0xFF0F172A),
                    ),
                    child: child!,
                  );
                },
              );

              if (picked != null) {
                // 2. Align to Monday
                final start = _getStartOfWeek(picked);
                
                // 3. AI PRE-CHECK: Mostra l'advisor prima di procedere
                bool proceed = true;
                final currentState = context.read<ScheduleBloc>().state;
                if (currentState is ScheduleLoaded) {
                  final s = currentState;
                  final result = await showDialog<bool>(
                    context: context,
                    builder: (context) => AiAdvisorDialog(
                      employees: s.employees,
                      activities: s.activities,
                      currentConfig: s.demandConfig,
                      startDate: start,
                      endDate: start.add(const Duration(days: 28)),
                    ),
                  );
                  proceed = result ?? false;
                }

                if (!proceed) return; // L'utente ha annullato o chiuso il dialogo

                // 4. Update View
                setState(() {
                  _visibleWeekStart = start;
                });
                
                // 5. Trigger Generation (4 Weeks)
                if (mounted) {
                   context.read<ScheduleBloc>().add(
                    GenerateSchedules(
                      start, 
                      start.add(const Duration(days: 28))
                    )
                  );
                }
              }
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
