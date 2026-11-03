// One shared production BRAM pool. Control grants either Conv or general port.
module stage5_memory(input wire clk,rst,conv_owner,
 input wire ar,wr,br,pr,cv,input wire [14:0] aa,wa,ba,
 input wire [6:0] bi,pi,input wire [15:0] weight_base,input wire [7:0] param_base,
 input wire [7:0] cd,input wire [31:0] ca,input wire [9:0] di,
 output wire [7:0] aq,wq,output wire [31:0] bq,mq,sq,
 input wire re,we,input wire [19:0] ra,xa,input wire [31:0] xd,
 output reg [31:0] q,input wire obs_we,input wire [8:0] obs_addr,input wire [31:0] obs_data,
 output reg signed [31:0] gap_m,output reg [31:0] gap_shift);
 wire [7:0] av,wv,bv;wire [31:0] biasv,mv,sv,dv;
 wire host=!conv_owner&&!rst;
 wire [15:0] cwa=weight_base+wa;
 wire [7:0] cbi=param_base+bi,cpi=param_base+pi;
 dense_ram #(.WIDTH(8),.DEPTH(32768),.AW(15)) A(clk,host&&we&&xa[19:16]==1,xa[14:0],xd[7:0],
 !rst&&((conv_owner&&ar)||(host&&re&&ra[19:16]==1)),conv_owner?aa:ra[14:0],av);
 dense_ram #(.WIDTH(8),.DEPTH(35904),.AW(16)) W(clk,host&&we&&xa>=20'h30000&&xa<20'h38c40,xa[15:0],xd[7:0],
 !rst&&((conv_owner&&wr)||(host&&re&&ra>=20'h30000&&ra<20'h38c40)),conv_owner?cwa:ra[15:0],wv);
 dense_ram #(.WIDTH(8),.DEPTH(32768),.AW(15)) B(clk,!rst&&((conv_owner&&cv)||(host&&we&&xa[19:16]==2)),conv_owner?ba:xa[14:0],conv_owner?cd:xd[7:0],host&&re&&ra[19:16]==2,ra[14:0],bv);
 dense_ram #(.WIDTH(32),.DEPTH(229),.AW(8)) BI(clk,host&&we&&xa>=20'h40000&&xa<20'h40394,xa[9:2],xd,
 !rst&&((conv_owner&&br)||(host&&re&&ra>=20'h40000&&ra<20'h40394)),conv_owner?cbi:ra[9:2],biasv);
 dense_ram #(.WIDTH(32),.DEPTH(229),.AW(8)) MU(clk,host&&we&&xa>=20'h41000&&xa<20'h41394,xa[9:2],xd,
 !rst&&((conv_owner&&pr)||(host&&re&&ra>=20'h41000&&ra<20'h41394)),conv_owner?cpi:ra[9:2],mv);
 dense_ram #(.WIDTH(32),.DEPTH(229),.AW(8)) SH(clk,host&&we&&xa>=20'h42000&&xa<20'h42394,xa[9:2],xd,
 !rst&&((conv_owner&&pr)||(host&&re&&ra>=20'h42000&&ra<20'h42394)),conv_owner?cpi:ra[9:2],sv);
 dense_ram #(.WIDTH(32),.DEPTH(512),.AW(9)) DEBUG(clk,!rst&&((conv_owner&&cv&&di<512)||(!conv_owner&&obs_we)),conv_owner?di[8:0]:obs_addr,conv_owner?ca:obs_data,
 host&&re&&ra>=20'h50000&&ra<20'h50800,ra[10:2],dv);
 assign aq=av;assign wq=wv;assign bq=biasv;assign mq=mv;assign sq=sv;
 always @* begin
 q=0;
 if(ra>=20'h10000&&ra<20'h18000)q={24'd0,av};
 else if(ra>=20'h20000&&ra<20'h28000)q={24'd0,bv};
 else if(ra>=20'h30000&&ra<20'h38c40)q={24'd0,wv};
 else if(ra>=20'h40000&&ra<20'h40394)q=biasv;
 else if(ra>=20'h41000&&ra<20'h41394)q=mv;
 else if(ra>=20'h42000&&ra<20'h42394)q=sv;
 else if(ra==20'h43000)q=gap_m;
 else if(ra==20'h43004)q=gap_shift;
 else if(ra>=20'h50000&&ra<20'h50800)q=dv;
 end
 always @(posedge clk)begin
 if(rst)begin gap_m<=0;gap_shift<=0;end
 else if(host&&we)begin if(xa==20'h43000)gap_m<=xd;if(xa==20'h43004)gap_shift<=xd;end
 end
endmodule
