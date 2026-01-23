import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';
import '../repositories/schedule_repository.dart';
import '../models/agent_models.dart';

// Events
abstract class ScheduleEvent extends Equatable {
  @override
  List<Object> get props => [];
}

class LoadInitialData extends ScheduleEvent {}
class LoadSchedules extends ScheduleEvent {}

class GenerateSchedules extends ScheduleEvent {
  final DateTime start;
  final DateTime end;
  GenerateSchedules(this.start, this.end);
}

class ToggleUnavailability extends ScheduleEvent {
  final String employeeId;
  final DateTime date;
  ToggleUnavailability(this.employeeId, this.date);
}

class UpdateDemandConfig extends ScheduleEvent {
  final DemandConfig config;
  UpdateDemandConfig(this.config);
}

class LearnDemand extends ScheduleEvent {}

class UpdateShift extends ScheduleEvent {
  final Map<String, dynamic> shift; // The original shift
  final DateTime newDate;
  final String newEmployeeId;
  UpdateShift({required this.shift, required this.newDate, required this.newEmployeeId});
}

// States
abstract class ScheduleState extends Equatable {
  @override
  List<Object> get props => [];
}

class ScheduleInitial extends ScheduleState {}
class ScheduleLoading extends ScheduleState {
  final String? message;
  ScheduleLoading({this.message});
  @override
  List<Object> get props => message != null ? [message!] : [];
}
class ScheduleLoaded extends ScheduleState {
  final List<dynamic> schedules;
  final List<dynamic> historicalSchedules;
  final List<Map<String, dynamic>> unavailabilities;
  final List<Employment> employees;
  final List<Activity> activities;
  final DemandConfig demandConfig;
  
  ScheduleLoaded(
    this.schedules, {
    this.historicalSchedules = const [],
    this.unavailabilities = const [],
    this.employees = const [],
    this.activities = const [],
    this.demandConfig = const DemandConfig(),
  });
  
  @override
  List<Object> get props => [schedules, historicalSchedules, unavailabilities, employees, activities, demandConfig];
}

class ScheduleError extends ScheduleState {
  final String message;
  ScheduleError(this.message);
}

// Bloc
class ScheduleBloc extends Bloc<ScheduleEvent, ScheduleState> {
  final ScheduleRepository repository;
  List<Map<String, dynamic>> _currentUnavailabilities = [];
  List<Employment> _currentEmployees = [];
  List<Activity> _currentActivities = [];
  DemandConfig _currentDemand = const DemandConfig();

  ScheduleBloc({required this.repository}) : super(ScheduleInitial()) {
    on<LoadInitialData>(_onLoadInitialData);
    on<LoadSchedules>(_onLoadSchedules);
    on<GenerateSchedules>(_onGenerateSchedules);
    on<ToggleUnavailability>(_onToggleUnavailability);
    on<UpdateDemandConfig>(_onUpdateDemandConfig);
    on<LearnDemand>(_onLearnDemand);
    on<UpdateShift>(_onUpdateShift);
  }

  Future<void> _onUpdateShift(UpdateShift event, Emitter<ScheduleState> emit) async {
    if (state is ScheduleLoaded) {
      final s = state as ScheduleLoaded;
      
      // 1. Update local schedule
      final updatedSchedules = List.from(s.schedules);
      if (updatedSchedules.isNotEmpty) {
        final scheduleMap = Map<String, dynamic>.from(updatedSchedules.first);
        final List<dynamic> shifts = List.from(scheduleMap['schedule'] ?? []);
        
        final shiftId = event.shift['id'];
        final idx = shifts.indexWhere((sh) => sh['id'] == shiftId);
        
        if (idx != -1) {
          final updatedShift = Map<String, dynamic>.from(shifts[idx]);
          final oldEmployeeId = updatedShift['employee_id'];
          
          updatedShift['employee_id'] = event.newEmployeeId;
          updatedShift['date'] = event.newDate.toIso8601String().split('T')[0];
          
          final newEmp = s.employees.firstWhere(
            (e) => e.id == event.newEmployeeId, 
            orElse: () => s.employees.first
          );
          updatedShift['employee_name'] = newEmp.fullName;
          
          shifts[idx] = updatedShift;
          scheduleMap['schedule'] = shifts;
          updatedSchedules[0] = scheduleMap;
          
          // 2. Persist to Firestore
          await repository.saveScheduleToFirestore(scheduleMap);
          
          // 3. Learning Loop
          // Log as manual "select" action
          repository.logFeedback(
            action: "select",
            selectedId: event.newEmployeeId,
            rejectedId: oldEmployeeId,
            shiftData: event.shift,
          );
          
          // Trigger background retraining to update Scorer weights in background
          repository.retrain();
          
          // 4. Emit updated state
          emit(ScheduleLoaded(
            updatedSchedules,
            historicalSchedules: s.historicalSchedules,
            unavailabilities: s.unavailabilities,
            employees: s.employees,
            activities: s.activities,
            demandConfig: s.demandConfig,
          ));
        }
      }
    }
  }

  void _onLoadInitialData(LoadInitialData event, Emitter<ScheduleState> emit) async {
    emit(ScheduleLoading(message: "Caricamento dati ambiente..."));
    _currentUnavailabilities = [];
    _currentEmployees = [];
    _currentActivities = [];
    try {
      _currentEmployees = await repository.getEmployment();
      _currentActivities = await repository.getActivities();
      
      // Load current demand profile/learned pattern
      final learned = await repository.learnDemand();
      _currentDemand = DemandConfig.fromJson(learned);
      
      // Auto-Learning: Trigger background retraining on app start/company change
      repository.retrain(); 
      
      add(LoadSchedules());
    } catch (e) {
      emit(ScheduleError("Failed to load initial data: $e"));
    }
  }

  void _onLoadSchedules(LoadSchedules event, Emitter<ScheduleState> emit) async {
    try {
      // Fetch historical data for comparison (last 30 days)
      final now = DateTime.now();
      final history = await repository.getHistoricalSchedule(
        now.subtract(const Duration(days: 30)),
        now.add(const Duration(days: 30)),
      );

      await emit.forEach(
        repository.getSchedules(),
        onData: (data) => ScheduleLoaded(
          data, 
          historicalSchedules: history,
          unavailabilities: _currentUnavailabilities,
          employees: _currentEmployees,
          activities: _currentActivities,
          demandConfig: _currentDemand,
        ),
        onError: (_, __) => ScheduleError("Failed to load schedules"),
      );
    } catch (e) {
      emit(ScheduleError(e.toString()));
    }
  }

  void _onGenerateSchedules(GenerateSchedules event, Emitter<ScheduleState> emit) async {
    emit(ScheduleLoading(message: "Caricamento dipendenti..."));
    try {
      // 0. Ensure we have employees loaded (critical!)
      if (_currentEmployees.isEmpty) {
        _currentEmployees = await repository.getEmployment();
        _currentActivities = await repository.getActivities();
      }
      
      if (_currentEmployees.isEmpty) {
        emit(ScheduleError("Nessun dipendente trovato per questa azienda. Impossibile generare turni."));
        return;
      }

      // 1. Wait for AI Brain Synchronization (Global Learning)
      emit(ScheduleLoading(message: "Sincronizzazione Cervello Globale..."));
      
      // Explicitly trigger retraining before generating, as requested
      try {
        await repository.retrain();
      } catch (e) {
        print("Retraining trigger failed (might be already running): $e");
      }

      int attempts = 0;
      bool isRunning = true;
      
      while (attempts < 180) { // Increased to 3 minutes for deep global training
        final status = await repository.getTrainingProgress();
        isRunning = status['status'] == 'running';
        final phase = status['phase'] ?? 'IDLE';
        final progress = (status['progress'] ?? 0.0) * 100;
        
        if (!isRunning && attempts > 2) break; // Ensure it actually started
        
        emit(ScheduleLoading(
          message: "L'IA sta imparando dai dati globali... (${progress.toStringAsFixed(0)}%)\nFase: $phase ($attempts s)"
        ));
        
        await Future.delayed(const Duration(seconds: 1));
        attempts++;
      }

      // 2. Trigger Generation with updated brains
      emit(ScheduleLoading(message: "Ottimizzazione neurale in corso..."));
      final scheduleData = await repository.triggerGeneration(
        startDate: event.start, 
        endDate: event.end,
        employees: _currentEmployees,
        activities: _currentActivities,
        unavailabilities: _currentUnavailabilities,
      );
      
      // 4. Save to Firestore for persistence
      await repository.saveScheduleToFirestore(scheduleData);
      
      final history = await repository.getHistoricalSchedule(
        event.start.subtract(const Duration(days: 7)),
        event.end.add(const Duration(days: 7)),
      );

      emit(ScheduleLoaded(
        [scheduleData], 
        historicalSchedules: history,
        unavailabilities: _currentUnavailabilities,
        employees: _currentEmployees,
        activities: _currentActivities,
      ));
    } catch (e) {
      emit(ScheduleError(e.toString()));
    }
  }

  void _onToggleUnavailability(ToggleUnavailability event, Emitter<ScheduleState> emit) {
    final dateStr = event.date.toIso8601String().split('T')[0];
    
    final existingIndex = _currentUnavailabilities.indexWhere(
      (u) => u['employee_id'] == event.employeeId && u['date'] == dateStr
    );

    if (existingIndex != -1) {
      _currentUnavailabilities.removeAt(existingIndex);
    } else {
      _currentUnavailabilities.add({
        'employee_id': event.employeeId,
        'date': dateStr,
      });
    }

    if (state is ScheduleLoaded) {
      final currentSchedules = (state as ScheduleLoaded).schedules;
      emit(ScheduleLoaded(
        currentSchedules, 
        unavailabilities: List.from(_currentUnavailabilities),
        employees: _currentEmployees,
        activities: _currentActivities,
        demandConfig: _currentDemand,
      ));
    }
  }

  void _onUpdateDemandConfig(UpdateDemandConfig event, Emitter<ScheduleState> emit) {
    _currentDemand = event.config;
    if (state is ScheduleLoaded) {
      final s = state as ScheduleLoaded;
      emit(ScheduleLoaded(
        s.schedules,
        unavailabilities: s.unavailabilities,
        employees: s.employees,
        activities: s.activities,
        demandConfig: _currentDemand,
      ));
    }
  }

  void _onLearnDemand(LearnDemand event, Emitter<ScheduleState> emit) async {
    try {
      final learnedConfig = await repository.learnDemand();
      add(UpdateDemandConfig(DemandConfig.fromJson(learnedConfig)));
    } catch (e) {
      print("Error learning demand details: $e");
    }
  }
}
