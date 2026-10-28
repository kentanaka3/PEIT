package init.peit.domain.model

data class TimePeriod(
    val startDate: String,
    val endDate: String,
    val label: String = "$startDate to $endDate"
) {
    companion object {
        fun ofMonth(yearMonth: String): TimePeriod {
            val normalized = yearMonth.trim()
            require(normalized.matches(Regex("^\\d{4}-(0[1-9]|1[0-2])$"))) {
                "Month must use YYYY-MM with a valid month."
            }
            val parts = normalized.split("-")
            val year = parts[0].toInt()
            val month = parts[1].toInt()
            require(year > 0) { "Month must use a year from 0001 through 9999." }
            val daysInMonth = when (month) {
                2 -> if ((year % 4 == 0 && year % 100 != 0) || (year % 400 == 0)) 29 else 28
                4, 6, 9, 11 -> 30
                else -> 31
            }
            val start = "%04d-%02d-01".format(year, month)
            val end = "%04d-%02d-%02d".format(year, month, daysInMonth)
            return TimePeriod(start, end, normalized)
        }

        fun ofYear(year: Int): TimePeriod {
            return TimePeriod("$year-01-01", "$year-12-31", year.toString())
        }

        fun between(startDate: String, endDate: String, label: String? = null): TimePeriod {
            val normStart = normalize(startDate, isEnd = false)
            val normEnd = normalize(endDate, isEnd = true)
            return TimePeriod(normStart, normEnd, label ?: "$normStart to $normEnd")
        }

        private fun normalize(dateStr: String, isEnd: Boolean): String {
            val trimmed = dateStr.trim()
            return when {
                trimmed.matches(Regex("^\\d{4}-\\d{2}-\\d{2}$")) -> trimmed
                trimmed.matches(Regex("^\\d{4}-\\d{2}$")) -> {
                    if (isEnd) ofMonth(trimmed).endDate else "$trimmed-01"
                }
                trimmed.matches(Regex("^\\d{4}$")) -> {
                    if (isEnd) "$trimmed-12-31" else "$trimmed-01-01"
                }
                else -> trimmed
            }
        }
    }

    fun contains(dateStr: String): Boolean {
        if (dateStr.isBlank()) return false
        val date = dateStr.take(10)
        return date >= startDate && date <= endDate
    }
}
