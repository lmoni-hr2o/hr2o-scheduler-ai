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

// States
abstract class ScheduleState extends Equatable {
  @override
  List<Object> get props => [];
}

class ScheduleInitial extends ScheduleState {}
class ScheduleLoading extends ScheduleState {}
class ScheduleLoaded extends ScheduleState {
  final List<dynamic> schedules;
  final List<Map<String, dynamic>> unavailabilities;
  final List<Employment> employees;
  final List<Activity> activities;
  final DemandConfig demandConfig;
  
  ScheduleLoaded(
    this.schedules, {
    this.unavailabilities = const [],
    this.employees = const [],
    this.activities = const [],
    this.demandConfig = const DemandConfig(),
  });
  
  @override
  List<Object> get props => [schedules, unavailabilities, employees, activities, demandConfig];
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
  }

  void _onLoadInitialData(LoadInitialData event, Emitter<ScheduleState> emit) async {
    emit(ScheduleLoading());
    try {
      _currentEmployees = await repository.getEmployment();
      _currentActivities = await repository.getActivities();
      add(LoadSchedules());
    } catch (e) {
      emit(ScheduleError("Failed to load initial data: $e"));
    }
  }

  void _onLoadSchedules(LoadSchedules event, Emitter<ScheduleState> emit) async {
    // Note: We don't emit Loading here if we already have initial data to avoid flickering
    try {
      await emit.forEach(
        repository.getSchedules(),
        onData: (data) => ScheduleLoaded(
          data, 
          unavailabilities: _currentUnavailabilities,
          employees: _currentEmployees,
          activities: _currentActivities,
        ),
        onError: (_, __) => ScheduleError("Failed to load schedules"),
      );
    } catch (e) {
      emit(ScheduleError(e.toString()));
    }
  }

  void _onGenerateSchedules(GenerateSchedules event, Emitter<ScheduleState> emit) async {
    emit(ScheduleLoading());
    try {
      final scheduleData = await repository.triggerGeneration(
        startDate: event.start, 
        endDate: event.end,
        employees: _currentEmployees,
        unavailabilities: _currentUnavailabilities,
      );
      emit(ScheduleLoaded(
        [scheduleData], 
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
      // Keep existing manual values if AI is disabled? 
      // No, this event is explicit "Learn Now" or auto-update.
      // We update the state.
      add(UpdateDemandConfig(learnedConfig));
    } catch (e) {
      print("Error learning demand details: $e");
    }
  }
}
