# Actual Stage5 synthesis and route only. Never write a bitstream or open hardware.
if {[llength $argv] != 2} {error "Usage: day2_build.tcl <sealed-source-snapshot> <new-absolute-build-dir>"}
set src [file normalize [lindex $argv 0]]
set dest [file normalize [lindex $argv 1]]
if {[file exists $dest]} {error "Refusing existing build directory"}
if {![file exists [file join [file dirname $src] rtl_gate.json]]} {error "RTL gate record missing"}
set gatefile [open [file join [file dirname $src] rtl_gate.json] r]
set gate [read $gatefile]
close $gatefile
if {![regexp {"status"\s*:\s*"PASS"} $gate]} {error "RTL gate not PASS"}
file mkdir $dest
set sources {}
foreach n {stage5_board_top stage5_top stage5_dense_core stage5_memory stage5_adapter stage5_control stage5_bridge dense_ram dense_fifo pe_mac requant_even stage3_uart p1_post_ops p1_requant} {
 set p [file join $src rtl ${n}.sv]
 if {![file isfile $p]} {error "Missing production source $p"}
 lappend sources $p
}
create_project stage5_day2 $dest -part xc7a35tfgg484-2
add_files $sources
add_files -fileset constrs_1 [file join $src constraints stage5.xdc]
set_property top stage5_board_top [current_fileset]
update_compile_order -fileset sources_1
launch_runs synth_1 -jobs 1
wait_on_run synth_1
set f [open $dest/run_status.txt w]
puts $f "synth: [get_property STATUS [get_runs synth_1]] [get_property PROGRESS [get_runs synth_1]]"
flush $f
if {[get_property STATUS [get_runs synth_1]] ne "synth_design Complete!"} {close $f;error "Synthesis not complete"}
launch_runs impl_1 -to_step route_design -jobs 1
wait_on_run impl_1
puts $f "impl: [get_property STATUS [get_runs impl_1]] [get_property PROGRESS [get_runs impl_1]]"
close $f
if {[get_property STATUS [get_runs impl_1]] ne "route_design Complete!"} {error "Route not complete"}
open_run impl_1
report_timing_summary -delay_type min_max -report_unconstrained -file $dest/timing.rpt
report_cdc -details -file $dest/cdc.rpt
report_drc -file $dest/drc.rpt
report_utilization -file $dest/resources.rpt
report_utilization -hierarchical -file $dest/resources_hierarchical.rpt
report_route_status -file $dest/route.rpt
check_timing -verbose -file $dest/check_timing.rpt
report_clocks -file $dest/clocks.rpt
report_exceptions -coverage -file $dest/exceptions.rpt
write_checkpoint $dest/routed.dcp
set setup [get_timing_paths -delay_type max -max_paths 1]
set hold [get_timing_paths -delay_type min -max_paths 1]
if {![llength $setup] || ![llength $hold]} {error "Missing timed paths"}
set bram18 [llength [get_cells -hier -filter {REF_NAME == RAMB18E1}]]
set bram36 [llength [get_cells -hier -filter {REF_NAME == RAMB36E1}]]
set f [open $dest/metrics.txt w]
puts $f "setup_slack=[get_property SLACK $setup]"
puts $f "hold_slack=[get_property SLACK $hold]"
puts $f "bram18=$bram18"
puts $f "bram36=$bram36"
puts $f "bram18_equivalent=[expr {$bram18+2*$bram36}]"
puts $f "clock_period=[get_property PERIOD [get_clocks sys_clk]]"
puts $f "reset_exception_pins=[llength [get_pins -hier -filter {NAME =~ *reset_sync_reg*/CLR}]]"
puts $f "rx_exception_pins=[llength [get_pins -hier -filter {NAME =~ *rx_sync_reg[0]/D}]]"
close $f
if {[get_property SLACK $setup]<0 || [get_property SLACK $hold]<0} {error "Setup/hold failed"}
if {$bram18+2*$bram36>80} {error "BRAM18 planning limit exceeded"}
puts "ROUTE_REPORTS_READY_REVIEW_REQUIRED"
