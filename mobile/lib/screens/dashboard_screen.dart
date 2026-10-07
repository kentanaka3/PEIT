import 'dart:math' as math;
import 'package:flutter/material.dart';

import '../data/database.dart';
import '../models/receipt_entry.dart';
import '../services/econometric_engine.dart';

/// Comprehensive, responsive Material 3 Dashboard screen for PEIT Mobile.
///
/// Features:
/// 1. Month Carousel Filter (All Time, YYYY-MM buttons).
/// 2. KPI Summary Cards (Net Cash Flow, Total Consumption, Personal Inflation Badge).
/// 3. Category Breakdown with pure Flutter CustomPainter Donut & legend.
/// 4. Price Index Trend card with line progression.
/// 5. Privacy & Local Compute badge.
class DashboardScreen extends StatefulWidget {
  final AppDatabase database;

  const DashboardScreen({
    super.key,
    required this.database,
  });

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  bool _isLoading = true;
  List<String> _availableMonths = [];
  String? _selectedMonth; // null = 'All Time'

  MonthlyCashFlowKpis? _cashFlowKpis;
  List<CategoryExpenditure> _categoryBreakdown = [];
  List<MonthlyIndexRecord> _indexRecords = [];
  MonthlyIndexRecord? _currentMonthIndexRecord;

  // Curated accessible color palette matching PEIT Dashboard
  static const List<Color> _categoryPalette = [
    Color(0xFF3B82F6), // Blue
    Color(0xFF10B981), // Emerald
    Color(0xFFF59E0B), // Amber
    Color(0xFFEF4444), // Red
    Color(0xFF8B5CF6), // Violet
    Color(0xFF06B6D4), // Cyan
    Color(0xFFEC4899), // Pink
    Color(0xFF84CC16), // Lime
    Color(0xFFF97316), // Orange
    Color(0xFF6366F1), // Indigo
    Color(0xFF14B8A6), // Teal
    Color(0xFFE11D48), // Rose
  ];

  @override
  void initState() {
    super.initState();
    _loadDashboardData();
  }

  Future<void> _loadDashboardData() async {
    setState(() => _isLoading = true);
    try {
      final months = await widget.database.getHistoricalMonths();
      final kpis = await widget.database.getMonthlyCashFlowKpis(month: _selectedMonth);
      final categories = await widget.database.getCategoryBreakdown(month: _selectedMonth);

      // Econometric calculations on all entries to derive multi-month price indices
      final allEntries = widget.database.getAllEntries();
      final indices = EconometricEngine.calculateMonthlyIndices(allEntries);

      MonthlyIndexRecord? selectedRecord;
      if (_selectedMonth != null) {
        selectedRecord = indices.cast<MonthlyIndexRecord?>().firstWhere(
              (r) => r?.month == _selectedMonth,
              orElse: () => null,
            );
      } else if (indices.isNotEmpty) {
        selectedRecord = indices.last; // latest month for overall summary
      }

      if (mounted) {
        setState(() {
          _availableMonths = months;
          _cashFlowKpis = kpis;
          _categoryBreakdown = categories;
          _indexRecords = indices;
          _currentMonthIndexRecord = selectedRecord;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error loading dashboard: $e'),
            backgroundColor: Colors.red.shade700,
          ),
        );
      }
    }
  }

  void _onSelectMonth(String? month) {
    if (_selectedMonth == month) return;
    setState(() {
      _selectedMonth = month;
    });
    _loadDashboardData();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Econometric Dashboard'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh KPIs',
            onPressed: _loadDashboardData,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadDashboardData,
              child: ListView(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                children: [
                  // 1. Month Carousel Selector
                  _buildMonthCarousel(colorScheme),
                  const SizedBox(height: 16),

                  // 2. Privacy & Local Compute Pill Reassurance
                  _buildPrivacyBadge(colorScheme),
                  const SizedBox(height: 16),

                  // 3. KPI Summary Cards Grid
                  _buildKpiSummaryCards(colorScheme),
                  const SizedBox(height: 16),

                  // 4. Category Breakdown Custom Donut & Legend
                  _buildCategoryBreakdownCard(theme, colorScheme),
                  const SizedBox(height: 16),

                  // 5. Price Index & Inflation Progression Card
                  _buildPriceIndexTrendCard(theme, colorScheme),
                  const SizedBox(height: 24),
                ],
              ),
            ),
    );
  }

  Widget _buildMonthCarousel(ColorScheme colorScheme) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          ChoiceChip(
            label: const Text('All Time'),
            selected: _selectedMonth == null,
            onSelected: (_) => _onSelectMonth(null),
            avatar: _selectedMonth == null
                ? const Icon(Icons.check, size: 16)
                : const Icon(Icons.all_inclusive, size: 16),
          ),
          const SizedBox(width: 8),
          ..._availableMonths.map((m) {
            final isSelected = _selectedMonth == m;
            return Padding(
              padding: const EdgeInsets.only(right: 8),
              child: ChoiceChip(
                label: Text(m),
                selected: isSelected,
                onSelected: (_) => _onSelectMonth(m),
                avatar: isSelected
                    ? const Icon(Icons.check, size: 16)
                    : const Icon(Icons.calendar_today, size: 14),
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _buildPrivacyBadge(ColorScheme colorScheme) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHighest.withOpacity(0.5),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: colorScheme.outlineVariant.withOpacity(0.5)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.shield_outlined, size: 16, color: colorScheme.primary),
          const SizedBox(width: 8),
          Flexible(
            child: Text(
              'Computed locally on device • Zero cloud transmission',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w500,
                color: colorScheme.onSurfaceVariant,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildKpiSummaryCards(ColorScheme colorScheme) {
    final kpis = _cashFlowKpis ??
        const MonthlyCashFlowKpis(
          totalIncome: 0,
          totalExpenditure: 0,
          netTransfers: 0,
          netRefunds: 0,
          netBalance: 0,
          transactionCount: 0,
        );

    final netPositive = kpis.netBalance >= 0;
    final mom = _currentMonthIndexRecord?.momPercent;

    return Column(
      children: [
        // Net Cash Flow Card
        Card(
          elevation: 2,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Net Cash Flow',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: colorScheme.onSurfaceVariant,
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: netPositive ? Colors.green.shade50 : Colors.red.shade50,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Row(
                        children: [
                          Icon(
                            netPositive ? Icons.arrow_upward : Icons.arrow_downward,
                            size: 14,
                            color: netPositive ? Colors.green.shade700 : Colors.red.shade700,
                          ),
                          const SizedBox(width: 4),
                          Text(
                            netPositive ? 'Surplus' : 'Deficit',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.bold,
                              color: netPositive ? Colors.green.shade700 : Colors.red.shade700,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  '${netPositive ? "+" : ""}\$${kpis.netBalance.toStringAsFixed(2)}',
                  style: TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.bold,
                    color: netPositive ? Colors.green.shade700 : Colors.red.shade700,
                  ),
                ),
                const SizedBox(height: 12),
                const Divider(),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    _buildSubKpi('Total Inflow', '+\$${kpis.totalIncome.toStringAsFixed(2)}', Colors.green.shade700),
                    _buildSubKpi('Total Outflow', '-\$${kpis.totalExpenditure.toStringAsFixed(2)}', Colors.red.shade700),
                    _buildSubKpi('Transactions', '${kpis.transactionCount}', colorScheme.onSurface),
                  ],
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),

        // Row of 2 Small Cards: Consumption Expenditure & Inflation MoM
        Row(
          children: [
            Expanded(
              child: Card(
                elevation: 1,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Consumption',
                        style: TextStyle(fontSize: 12, color: colorScheme.onSurfaceVariant),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        '\$${kpis.totalExpenditure.toStringAsFixed(2)}',
                        style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Recurring & One-off',
                        style: TextStyle(fontSize: 10, color: colorScheme.outline),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Card(
                elevation: 1,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Personal Inflation',
                        style: TextStyle(fontSize: 12, color: colorScheme.onSurfaceVariant),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        mom != null ? '${mom >= 0 ? "+" : ""}${mom.toStringAsFixed(2)}%' : 'Base Month',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: mom == null
                              ? colorScheme.primary
                              : (mom > 0 ? Colors.red.shade700 : Colors.green.shade700),
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        mom != null ? 'Month-over-Month' : '100.0 Fixed Basket',
                        style: TextStyle(fontSize: 10, color: colorScheme.outline),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildSubKpi(String label, String value, Color color) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 11, color: Colors.grey)),
        const SizedBox(height: 2),
        Text(value, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: color)),
      ],
    );
  }

  Widget _buildCategoryBreakdownCard(ThemeData theme, ColorScheme colorScheme) {
    if (_categoryBreakdown.isEmpty) {
      return Card(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        child: const Padding(
          padding: EdgeInsets.all(24),
          child: Center(
            child: Text('No consumption transactions recorded for this period.'),
          ),
        ),
      );
    }

    final totalSpent = _categoryBreakdown.fold<double>(0.0, (acc, item) => acc + item.totalSpent);

    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'Spending by Category',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
                Text(
                  '\$${totalSpent.toStringAsFixed(2)}',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                    color: colorScheme.primary,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Donut Chart Custom Painter
            Center(
              child: SizedBox(
                width: 170,
                height: 170,
                child: CustomPaint(
                  painter: _DonutChartPainter(
                    breakdown: _categoryBreakdown,
                    palette: _categoryPalette,
                  ),
                  child: Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          '${_categoryBreakdown.length}',
                          style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                        ),
                        Text(
                          'Categories',
                          style: TextStyle(fontSize: 11, color: colorScheme.outline),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 20),

            // Segmented percentage progress bar
            ClipRRect(
              borderRadius: BorderRadius.circular(6),
              child: SizedBox(
                height: 8,
                child: Row(
                  children: _categoryBreakdown.asMap().entries.map((entry) {
                    final idx = entry.key;
                    final item = entry.value;
                    final color = _categoryPalette[idx % _categoryPalette.length];
                    return Expanded(
                      flex: (item.percentage * 10).round().clamp(1, 1000),
                      child: Container(color: color),
                    );
                  }).toList(),
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Category Details List
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: _categoryBreakdown.length,
              separatorBuilder: (_, __) => const Divider(height: 12),
              itemBuilder: (context, index) {
                final item = _categoryBreakdown[index];
                final color = _categoryPalette[index % _categoryPalette.length];

                return Row(
                  children: [
                    Container(
                      width: 12,
                      height: 12,
                      decoration: BoxDecoration(
                        color: color,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            item.category,
                            style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                          ),
                          Text(
                            '${item.itemCount} items',
                            style: TextStyle(fontSize: 11, color: colorScheme.outline),
                          ),
                        ],
                      ),
                    ),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text(
                          '\$${item.totalSpent.toStringAsFixed(2)}',
                          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                        ),
                        Text(
                          '${item.percentage.toStringAsFixed(1)}%',
                          style: TextStyle(fontSize: 11, color: colorScheme.outline),
                        ),
                      ],
                    ),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPriceIndexTrendCard(ThemeData theme, ColorScheme colorScheme) {
    if (_indexRecords.isEmpty) {
      return const SizedBox.shrink();
    }

    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'Price Index Progression',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: colorScheme.primaryContainer,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    'Base: 100.0',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                      color: colorScheme.onPrimaryContainer,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              'Matched Laspeyres fixed-basket trajectory over chronological months.',
              style: TextStyle(fontSize: 12, color: colorScheme.outline),
            ),
            const SizedBox(height: 16),

            // Price Index Custom Painter Line Chart
            SizedBox(
              height: 120,
              width: double.infinity,
              child: CustomPaint(
                painter: _PriceTrendLinePainter(
                  records: _indexRecords,
                  lineColor: colorScheme.primary,
                  gridColor: colorScheme.outlineVariant.withOpacity(0.5),
                ),
              ),
            ),
            const SizedBox(height: 14),

            // Monthly Progression Table
            ..._indexRecords.map((r) {
              final idx = r.fixedBasketIndex;
              final mom = r.momPercent;
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(r.month, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
                    Row(
                      children: [
                        Text(
                          idx != null ? idx.toStringAsFixed(2) : 'N/A',
                          style: const TextStyle(fontFamily: 'monospace', fontSize: 13),
                        ),
                        const SizedBox(width: 12),
                        Container(
                          width: 65,
                          alignment: Alignment.centerRight,
                          child: Text(
                            mom != null ? '${mom >= 0 ? "+" : ""}${mom.toStringAsFixed(2)}%' : 'Base',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.bold,
                              color: mom == null
                                  ? colorScheme.outline
                                  : (mom > 0 ? Colors.red.shade700 : Colors.green.shade700),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              );
            }),
          ],
        ),
      ),
    );
  }
}

/// CustomPainter for rendering high-performance Circular Donut Charts without external dependencies.
class _DonutChartPainter extends CustomPainter {
  final List<CategoryExpenditure> breakdown;
  final List<Color> palette;

  _DonutChartPainter({
    required this.breakdown,
    required this.palette,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (breakdown.isEmpty) return;

    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) / 2;
    const strokeWidth = 24.0;

    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.butt;

    double startAngle = -math.pi / 2; // start from top (12 o'clock)

    for (int i = 0; i < breakdown.length; i++) {
      final item = breakdown[i];
      final sweepAngle = (item.percentage / 100.0) * (2 * math.pi);
      paint.color = palette[i % palette.length];

      canvas.drawArc(
        Rect.fromCircle(center: center, radius: radius - (strokeWidth / 2)),
        startAngle,
        sweepAngle,
        false,
        paint,
      );

      startAngle += sweepAngle;
    }
  }

  @override
  bool shouldRepaint(covariant _DonutChartPainter oldDelegate) {
    return oldDelegate.breakdown != breakdown;
  }
}

/// CustomPainter for rendering Price Index Progression line chart.
class _PriceTrendLinePainter extends CustomPainter {
  final List<MonthlyIndexRecord> records;
  final Color lineColor;
  final Color gridColor;

  _PriceTrendLinePainter({
    required this.records,
    required this.lineColor,
    required this.gridColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (records.isEmpty) return;

    final validValues = records
        .map((r) => r.fixedBasketIndex)
        .where((v) => v != null)
        .cast<double>()
        .toList();

    if (validValues.isEmpty) return;

    final double minVal = (validValues.reduce(math.min) * 0.98).clamp(0.0, double.infinity);
    final double maxVal = validValues.reduce(math.max) * 1.02;
    final double valRange = maxVal > minVal ? maxVal - minVal : 1.0;

    // Background horizontal guideline
    final gridPaint = Paint()
      ..color = gridColor
      ..strokeWidth = 1.0;
    canvas.drawLine(Offset(0, size.height / 2), Offset(size.width, size.height / 2), gridPaint);
    canvas.drawLine(Offset(0, size.height), Offset(size.width, size.height), gridPaint);

    final linePaint = Paint()
      ..color = lineColor
      ..strokeWidth = 3.0
      ..style = PaintingStyle.stroke;

    final dotPaint = Paint()
      ..color = lineColor
      ..style = PaintingStyle.fill;

    final path = Path();
    final points = <Offset>[];

    final dxStep = records.length > 1 ? size.width / (records.length - 1) : size.width / 2;

    for (int i = 0; i < records.length; i++) {
      final val = records[i].fixedBasketIndex ?? 100.0;
      final normalizedY = 1.0 - ((val - minVal) / valRange);
      final x = records.length > 1 ? i * dxStep : size.width / 2;
      final y = (normalizedY * (size.height - 16)) + 8; // padding top & bottom

      final point = Offset(x, y);
      points.add(point);

      if (i == 0) {
        path.moveTo(point.dx, point.dy);
      } else {
        path.lineTo(point.dx, point.dy);
      }
    }

    canvas.drawPath(path, linePaint);

    for (final pt in points) {
      canvas.drawCircle(pt, 4.0, dotPaint);
    }
  }

  @override
  bool shouldRepaint(covariant _PriceTrendLinePainter oldDelegate) {
    return oldDelegate.records != records;
  }
}

