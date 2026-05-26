import 'package:intl/intl.dart';

final _dateFmt = DateFormat('dd MMM yyyy');
final _dateTimeFmt = DateFormat('dd MMM yyyy, HH:mm');

String formatDate(DateTime? dt) => dt == null ? '—' : _dateFmt.format(dt.toLocal());
String formatDateTime(DateTime? dt) => dt == null ? '—' : _dateTimeFmt.format(dt.toLocal());

String formatRelative(DateTime? dt) {
  if (dt == null) return '—';
  final diff = DateTime.now().difference(dt.toLocal());
  if (diff.inDays == 0) return 'Today';
  if (diff.inDays == 1) return 'Yesterday';
  if (diff.inDays < 7) return '${diff.inDays} days ago';
  return formatDate(dt);
}
